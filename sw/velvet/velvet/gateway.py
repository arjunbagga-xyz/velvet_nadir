"""
Gateway orchestrator for Velvet Nadir.

The Gateway is the central brain that:
1. Receives events from stream monitors (wake word, speech, etc.)
2. Enqueues them as prioritized requests
3. Worker coroutines process requests concurrently
4. Routes tasks to appropriate skills via LLM or direct execution
"""

__all__ = [
    "Gateway",
    "get_gateway",
    "init_gateway",
]

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from enum import Enum
from loguru import logger

from .context import ContextManager, EngagementLevel, get_context_manager
from .skills import SkillRegistry, SkillResult, AutonomyLevel, get_skill_registry
from .fabric import VelvetMessage, MessageType, get_fabric
from .tool_parsing import extract_tool_calls, extract_text_response
from .config import get_config
from .agents import AgentOrchestrator
from .shen.yi import Yi
from .shen.xi import Xi, XiJournal
from .shen.fuxi import Fuxi
from .shen.agni import Agni
from velvet.reliability import strip_think_blocks


# Priority levels (lower number = higher priority)
class Priority:
    CRITICAL = 1   # Safety alerts, interrupts
    HIGH = 3       # User-initiated actions
    NORMAL = 5     # Standard voice commands
    LOW = 7        # Background tasks, proactive suggestions
    IDLE = 9       # Housekeeping


@dataclass(order=True)
class GatewayRequest:
    """A request to be processed by the gateway."""
    priority: int
    # Fields below are excluded from ordering
    request_type: str = field(compare=False)  # "wake", "transcript", "skill"
    payload: dict = field(default_factory=dict, compare=False)
    correlation_id: str = field(default="", compare=False)
    cancel: asyncio.Event = field(default_factory=asyncio.Event, compare=False)
    _seq: int = field(default=0, compare=True)  # Tie-breaker for same priority


class GatewayState(Enum):
    """Current state of the Gateway."""
    IDLE = "idle"                  # Waiting for wake trigger
    LISTENING = "listening"        # Actively listening for speech
    PROCESSING = "processing"      # Processing user input with LLM
    EXECUTING = "executing"        # Executing a skill
    SPEAKING = "speaking"          # TTS output in progress


@dataclass
class PendingAction:
    """An action awaiting user approval (for Level 2 autonomy)."""
    skill_name: str
    params: dict[str, Any]
    description: str
    correlation_id: str


# Type for LLM inference function
LLMInferenceFunc = Callable[[str, list[dict], list[dict] | None], Awaitable[str]]


class Gateway:
    """
    Central orchestrator for Velvet Nadir.

    Uses an asyncio.PriorityQueue with worker coroutines for concurrent
    request processing. Multiple workers can handle requests simultaneously,
    while a TTS lock prevents overlapping speech output.

    Coordinates between:
    - Stream monitors (audio VAD, wake word, vision)
    - Context manager (tracks, memory)
    - LLM inference (manager model)
    - Skill execution
    """

    def __init__(
        self,
        context_manager: ContextManager | None = None,
        skill_registry: SkillRegistry | None = None,
        llm_inference: LLMInferenceFunc | None = None,
        autonomy_level: AutonomyLevel | None = None,
        max_workers: int = 2,
        vision_enabled: bool = True,
    ):
        self.context = context_manager or get_context_manager()
        self.skills = skill_registry or get_skill_registry()
        self.llm_inference = llm_inference
        
        # Read autonomy from config if not provided
        if autonomy_level is not None:
            self.autonomy_level = autonomy_level
        else:
            self.autonomy_level = AutonomyLevel.LEVEL_2

        self.state = GatewayState.IDLE
        self.pending_actions: list[PendingAction] = []
        self._running = False

        # Queue and workers (bounded to prevent unbounded memory growth)
        self._queue: asyncio.PriorityQueue[GatewayRequest] = asyncio.PriorityQueue(maxsize=50)
        self._workers: list[asyncio.Task] = []
        self._max_workers = max_workers
        self._seq_counter = 0  # Monotonic counter for tie-breaking

        # Cancel support — tracks active request cancel events
        self._active_cancels: list[asyncio.Event] = []

        # LLM timeout from config
        self._llm_timeout = get_config().llm.timeout_sec

        # TTS serialization lock — prevents overlapping speech
        self._tts_lock = asyncio.Lock()
        self._tts_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=20)
        self._tts_worker: asyncio.Task | None = None

        # Project Shen: Cognitive Core
        self.agent_orchestrator = AgentOrchestrator()
        from velvet.limen import get_limen_gateway
        self.limen_gateway = get_limen_gateway(self.agent_orchestrator)
        self._trust_engine = None
        self.yi = Yi(start_vision_monitor=vision_enabled, llm_inference=llm_inference)
        self.xi = self._init_xi()
        self.yi._xi = self.xi

    async def start(self) -> None:
        """Start the Gateway, spawn workers, and subscribe to events."""
        self._running = True

        # Spawn worker coroutines
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker_loop(i), name=f"gw-worker-{i}")
            self._workers.append(task)

        # Spawn decoupled TTS worker
        self._tts_worker = asyncio.create_task(self._tts_worker_loop(), name="gw-tts-worker")

        # Subscribe to fabric events
        fabric = get_fabric()
        await fabric.subscribe(MessageType.WAKE_WORD.value, self._on_wake_word)
        await fabric.subscribe(MessageType.TRANSCRIPT.value, self._on_transcript)
        await fabric.subscribe(MessageType.SPEECH_END.value, self._on_speech_end)
        await fabric.subscribe(MessageType.SKILL_REQUEST.value, self._on_skill_request)
        await fabric.subscribe(MessageType.CANCEL_REQUEST.value, self._on_cancel_request)
        await fabric.subscribe(MessageType.VISION_EVENT.value, self._on_vision_event)
        await fabric.subscribe(MessageType.DISPLAY_CHAT_IN.value, self._on_chat_in)
        await fabric.subscribe(MessageType.SKILL_PENDING_APPROVAL.value, self._on_skill_pending_approval)
        await fabric.subscribe(MessageType.ESTOP.value, self._on_estop)

        # Wire AgentOrchestrator to the mesh
        await self.agent_orchestrator.bind_fabric(fabric)

        logger.info(f"Gateway started with {self._max_workers} workers, timeout={self._llm_timeout}s")

    async def stop(self) -> None:
        """Stop the Gateway and cancel workers."""
        self._running = False

        # Flush Xi (final breathe before shutdown)
        if self.xi:
            try:
                await self.xi.flush()
            except Exception as e:
                logger.error(f"Xi flush failed during shutdown: {e}")

        # Cancel TTS worker
        if self._tts_worker:
            self._tts_worker.cancel()
            try:
                await self._tts_worker
            except (asyncio.CancelledError, Exception):
                pass
            self._tts_worker = None

        # Cancel all workers
        for task in self._workers:
            task.cancel()

        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("Gateway stopped")

    # =========================================================================
    # Worker Loop
    # =========================================================================

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker coroutine that pulls requests from the queue."""
        logger.debug(f"Worker {worker_id} started")

        while self._running:
            try:
                request = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                logger.debug(f"Worker {worker_id} processing {request.request_type} "
                           f"(priority={request.priority})")
                # Track cancel event so it can be triggered externally
                self._active_cancels.append(request.cancel)
                await self._process_request(request)
            except Exception as e:
                logger.error(f"Worker {worker_id} error processing {request.request_type}: {e}")
            finally:
                if request.cancel in self._active_cancels:
                    self._active_cancels.remove(request.cancel)
                self._queue.task_done()

        logger.debug(f"Worker {worker_id} stopped")

    async def _process_request(self, request: GatewayRequest) -> None:
        """Route a request to the appropriate handler."""
        if request.request_type == "wake":
            await self._handle_wake()
        elif request.request_type == "transcript":
            text = request.payload.get("text", "")
            if text.strip():
                await self._process_input(text, cancel=request.cancel)
        elif request.request_type == "skill":
            skill_name = request.payload.get("skill", "")
            params = request.payload.get("params", {})
            correlation_id = request.payload.get("correlation_id")
            result = await self.execute_skill(skill_name, params)
            if correlation_id:
                try:
                    from velvet.fabric import get_fabric, MessageType
                    fabric = get_fabric()
                    await fabric.publish(
                        MessageType.SKILL_RESPONSE.value,
                        {
                            "correlation_id": correlation_id,
                            "skill": skill_name,
                            "status": "success" if result.success else "error",
                            "data": result.data,
                            "error": result.error,
                        }
                    )
                except Exception as e:
                    logger.error(f"[Gateway] Failed to publish SKILL_RESPONSE: {e}")

    # =========================================================================
    # Event Handlers (enqueue instead of process directly)
    # =========================================================================

    async def _on_wake_word(self, msg: VelvetMessage) -> None:
        """Handle wake word detection."""
        if self.state != GatewayState.IDLE:
            logger.debug("Already active, ignoring wake word")
            return

        self._enqueue(GatewayRequest(
            priority=Priority.HIGH,
            request_type="wake",
        ))

    async def _on_transcript(self, msg: VelvetMessage) -> None:
        """Handle speech transcript (user input)."""
        transcript = msg.payload.get("text", "")
        is_final = msg.payload.get("is_final", True)

        if not is_final or not transcript.strip():
            return

        logger.info(f"User said: {transcript}")
        self.context.add_conversation_message("user", transcript)

        self._enqueue(GatewayRequest(
            priority=Priority.NORMAL,
            request_type="transcript",
            payload={"text": transcript},
        ))

    async def _on_speech_end(self, msg: VelvetMessage) -> None:
        """Handle end of speech (silence detected)."""
        # This could trigger processing if we were buffering
        pass

    async def _on_skill_request(self, msg: VelvetMessage) -> None:
        """Handle skill execution request routed through the fabric."""
        skill_name = msg.payload.get("skill", "")
        params = msg.payload.get("params", {})
        correlation_id = msg.payload.get("correlation_id")
        if not skill_name:
            logger.warning("Received skill request with no skill name")
            return
        logger.info(f"Skill request via fabric: {skill_name} (source={msg.payload.get('source', 'unknown')})")
        self._enqueue(GatewayRequest(
            priority=Priority.HIGH,
            request_type="skill",
            payload={"skill": skill_name, "params": params, "correlation_id": correlation_id},
        ))

    async def _on_cancel_request(self, msg: VelvetMessage) -> None:
        """Handle cancel request — abort all in-progress LLM calls."""
        count = len(self._active_cancels)
        if count == 0:
            logger.info("Cancel requested but nothing is in progress")
            return
        logger.info(f"Cancel requested, signalling {count} active request(s)")
        for cancel_event in self._active_cancels:
            cancel_event.set()

    async def _on_vision_event(self, msg: VelvetMessage) -> None:
        """Handle vision events from a remote monitor."""
        image_b64 = msg.payload.get("image")
        score = msg.payload.get("score", 0.0)
        
        if image_b64:
             await self.yi.on_vision_event(image_b64, score)
        
    async def _on_chat_in(self, msg: VelvetMessage) -> None:
        """Handle incoming chat from the Display UI."""
        text = msg.payload.get("text")
        if text:
            logger.info(f"[Gateway] Received UI chat: {text}")
            self.context.add_conversation_message("user", text)
            self._enqueue(GatewayRequest(
                priority=Priority.NORMAL,
                request_type="transcript",
                payload={"text": text},
            ))

    async def _on_skill_pending_approval(self, msg: VelvetMessage) -> None:
        """Handle a notification that a new skill is pending approval."""
        payload = msg.payload
        skill_name = payload.get("skill_name")
        description = payload.get("description")
        logger.info(f"[Gateway] New skill pending approval: {skill_name} ({description})")
        if self.state == GatewayState.IDLE:
            await self._speak(
                f"I noticed you've been doing some tasks repeatedly. I've drafted a new skill called "
                f"{skill_name} to automate this. Should I enable it?"
            )

    async def _on_estop(self, msg: VelvetMessage) -> None:
        """Handle emergency stop message: abort all active tasks, drain queues, clear speech."""
        logger.warning("[Gateway] EMERGENCY STOP (ESTOP) engaged!")
        for cancel_event in self._active_cancels:
            cancel_event.set()

        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                break

        while not self._tts_queue.empty():
            try:
                self._tts_queue.get_nowait()
                self._tts_queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                break

        await self.reset_state()
        logger.warning("[Gateway] ESTOP complete: queues drained, state reset to IDLE.")

    async def reset_state(self) -> None:
        """Reset gateway state to IDLE and re-check context engagement."""
        self.state = GatewayState.IDLE
        if self.context:
            await self.context.set_engagement(EngagementLevel.MONITORING)

    def _enqueue(self, request: GatewayRequest) -> None:
        """Add a request to the priority queue with a monotonic sequence number."""
        self._seq_counter += 1
        request._seq = self._seq_counter
        try:
            self._queue.put_nowait(request)
        except asyncio.QueueFull:
            logger.warning(
                f"[Gateway] Request queue full (maxsize=50). Dropping request: {request.request_type} "
                f"(priority={request.priority})"
            )

    # =========================================================================
    # Request Processing
    # =========================================================================

    async def _handle_wake(self) -> None:
        """Handle wake word activation."""
        self.state = GatewayState.LISTENING
        await self.context.set_engagement(EngagementLevel.ACTIVE)
        logger.info("Wake word detected, now listening")
        await self._speak("I'm listening")

    async def _process_input(self, user_input: str, cancel: asyncio.Event | None = None) -> None:
        """Process user input through Yi (The Intent/Arbiter)."""
        try:
            from velvet.privacy import PrivacyClassifier
            classifier = PrivacyClassifier()
            level = classifier.classify(user_input)
            self.context.current_privacy_level = level
            logger.debug(f"[Gateway] Classified input privacy level: {level.name}")
        except Exception as e:
            logger.debug(f"[Gateway] Failed to classify user input: {e}")
            
        self.state = GatewayState.PROCESSING
        try:
            # PROJECT SHEN: Unified Cognition
            # All input is routed through Yi, which consults Jing (Memory) and routes to Po/Hun.
            # The Gateway is now just the nervous system coordinator.
            
            logger.info(f"Gateway dispatching to Yi: {user_input}")

            # Call Yi with timeout protection
            # We don't pass 'tools' here because Hun retrieves them from the registry itself.
            response = await asyncio.wait_for(
                self.yi.dispatch(user_input), 
                timeout=30.0
            )

            # Check for cancellation before speaking
            if cancel and cancel.is_set():
                logger.info("Request cancelled during Yi processing")
                return

            # Parse for tool calls, then speak or execute
            await self._handle_llm_response(response)

        except asyncio.TimeoutError:
            logger.warning("Yi timed out")
            await self._speak("I'm thinking too hard. One moment.")
        except Exception as e:
            logger.error(f"Error in _process_input: {e}", exc_info=True)
            await self._speak("I encountered an error processing that.")
        finally:
            self.state = GatewayState.LISTENING
            await self.context.set_engagement(EngagementLevel.MONITORING)

            # Trigger context compression check at conversation boundary
            try:
                await self.context.compress_context_if_needed()
            except Exception as e:
                logger.error(f"[Gateway] Context compression failed: {e}")

            # Trigger Xi breathe at conversation boundary
            if self.xi:
                asyncio.create_task(self._xi_breathe_safe())



    async def _handle_llm_response(self, response: str) -> None:
        """
        Handle LLM response, parsing and executing tool calls.

        Uses tool_parsing module for extraction.
        """
        response = strip_think_blocks(str(response))
        tool_calls = extract_tool_calls(response)

        if not tool_calls:
            # Check StopGateEngine if an active task is IN_PROGRESS
            try:
                from velvet.shen.stop_gates import StopGateEngine
                from velvet.task_graph import TaskState
                task_graph = getattr(self, "task_graph", None) or getattr(self.context, "task_graph", None)
                if task_graph and hasattr(task_graph, "tasks"):
                    active_task = next((t for t in task_graph.tasks.values() if t.state == TaskState.IN_PROGRESS), None)
                    if active_task:
                        stop_gate = StopGateEngine()
                        intercepted, nudge = stop_gate.intercept_turn(response, active_task)
                        if intercepted and nudge:
                            logger.warning(f"[Gateway] StopGate intercepted turn for active task '{active_task.name}'")
                            self.context.add_conversation_message("user", nudge)
                            await self._speak("Task still in progress: please complete or block the task.")
                            return
            except Exception as e:
                logger.debug(f"[Gateway] StopGate check bypassed: {e}")

            # Plain text response, just speak it
            self.context.add_conversation_message("assistant", response)
            await self._speak(response)
            return

        # Execute each tool call
        tool_results = []
        for call in tool_calls:
            skill_name = call.get("tool") or call.get("name") or call.get("function")
            params = call.get("params") or call.get("arguments") or call.get("parameters", {})

            if not skill_name:
                logger.warning(f"Invalid tool call format: {call}")
                continue

            logger.info(f"Executing tool: {skill_name} with params: {params}")
            result = await self.execute_skill(skill_name, params)

            tool_results.append({
                "tool": skill_name,
                "success": result.success,
                "data": result.data,
                "error": result.error,
            })

            # If skill has speech output, don't double-speak
            if result.speak:
                self.context.add_conversation_message("assistant", result.speak)

        # If we had tool calls but no speech output yet, generate summary
        if tool_results and not any(r.get("speak") for r in tool_results):
            text_response = extract_text_response(response)
            if text_response:
                clean_text = strip_think_blocks(text_response)
                self.context.add_conversation_message("assistant", clean_text)
                await self._speak(clean_text)

    # =========================================================================
    # TTS (Decoupled background worker + serialized lock)
    # =========================================================================

    async def _tts_worker_loop(self) -> None:
        """Background worker that pulls TTS items from _tts_queue and speaks sequentially."""
        logger.debug("TTS worker started")
        while self._running:
            try:
                text = await asyncio.wait_for(self._tts_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                await self._do_speak(text)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Gateway] Error in TTS worker: {e}")
            finally:
                self._tts_queue.task_done()
        logger.debug("TTS worker stopped")

    async def _speak(self, text: str, await_completion: bool = False) -> None:
        """Send text to TTS with think block scrubbing. Decoupled from caller worker."""
        clean_text = strip_think_blocks(text).strip()
        if not clean_text:
            return

        if await_completion:
            await self._do_speak(clean_text)
        else:
            try:
                self._tts_queue.put_nowait(clean_text)
            except asyncio.QueueFull:
                logger.warning(f"[Gateway] TTS queue full. Dropping TTS speech: {clean_text[:40]}...")

    async def _do_speak(self, text: str) -> None:
        """Perform TTS speaking under serialization lock, awaiting completion."""
        async with self._tts_lock:
            prev_state = self.state
            self.state = GatewayState.SPEAKING

            fabric = get_fabric()
            
            # Set up a completion event before publishing
            done = asyncio.Event()
            
            async def _on_tts_done(msg):
                done.set()
            
            # Subscribe for TTS completion signal
            await fabric.subscribe(MessageType.TTS_DONE.value, _on_tts_done)
            
            # Publish the TTS request
            await fabric.publish(
                MessageType.TTS_SPEAK.value,
                {"text": text}
            )
            
            # Send to UI Display
            await fabric.publish(
                MessageType.DISPLAY_CHAT_OUT.value,
                {"text": text}
            )

            # Wait for playback to finish (with timeout)
            try:
                await asyncio.wait_for(done.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                logger.warning(f"TTS playback timed out for: {text[:50]}...")
            finally:
                await fabric.unsubscribe(MessageType.TTS_DONE.value, _on_tts_done)

            logger.debug(f"TTS complete: {text[:50]}...")
            self.state = prev_state

    # =========================================================================
    # Skill Execution
    # =========================================================================

    async def execute_skill(self, skill_name: str, params: dict[str, Any], silent: bool = False) -> SkillResult:
        """Execute a skill by name."""
        skill = self.skills.get(skill_name)
        if not skill:
            # Check if this is an external MCP tool routed via LimenGateway
            if hasattr(self, "limen_gateway") and self.limen_gateway:
                mcp_schemas = getattr(self.limen_gateway, "mcp_tool_schemas", {})
                is_mcp = False
                if isinstance(mcp_schemas, dict):
                    is_mcp = skill_name in mcp_schemas
                elif isinstance(mcp_schemas, list):
                    is_mcp = any(
                        isinstance(s, dict) and s.get("function", {}).get("name") == skill_name
                        for s in mcp_schemas
                    )
                if is_mcp:
                    try:
                        logger.info(f"Routing external MCP tool execution to LimenGateway: {skill_name}")
                        res = await self.limen_gateway.execute_mcp_tool(skill_name, params)
                        if isinstance(res, dict) and res.get("status") == "error":
                            return SkillResult.fail(res.get("error", "MCP tool execution failed"))
                        return SkillResult.ok(data=res)
                    except Exception as mcp_err:
                        logger.warning(f"LimenGateway MCP tool routing failed: {mcp_err}")
                        return SkillResult.fail(f"MCP tool error: {mcp_err}")
            return SkillResult.fail(f"Unknown skill: {skill_name}")

        defn = skill.definition

        # Check autonomy level BEFORE preprocessing or executing
        if defn.autonomy_required.value > self.autonomy_level.value:
            import uuid
            corr_id = str(uuid.uuid4())[:8]
            pending = PendingAction(
                correlation_id=corr_id,
                action_type=skill_name,
                payload=params,
                autonomy_required=defn.autonomy_required,
            )
            self.pending_actions.append(pending)
            
            try:
                from velvet.fabric import get_fabric, MessageType
                fabric = get_fabric()
                await fabric.publish(
                    MessageType.SKILL_PENDING_APPROVAL.value,
                    {
                        "correlation_id": corr_id,
                        "skill_name": skill_name,
                        "params": params,
                        "autonomy_required": defn.autonomy_required.name
                    }
                )
            except Exception as e:
                logger.error(f"[Gateway] Failed to publish pending approval: {e}")

            return SkillResult.fail(
                f"Skill {skill_name} requires autonomy level {defn.autonomy_required.name} (pending approval id: {corr_id})"
            )

        # Preprocess parameters via Armature (inject configs & interpolate env vars)
        from velvet.skills import Armature
        params = Armature.preprocess(skill, params)

        # Validate parameters
        valid, error = await skill.validate_params(**params)
        if not valid:
            return SkillResult.fail(error or "Invalid parameters")

        # Execute
        import time
        start_t = time.perf_counter()
        try:
            logger.info(f"Executing skill: {skill_name}")
            result = await skill.execute(**params)
            duration_ms = (time.perf_counter() - start_t) * 1000
            self.skills.record_execution(skill_name, result.success, duration_ms)

            if result.speak and not silent:
                await self._speak(result.speak)

            if hasattr(self, "_display_bridge") and self._display_bridge and getattr(result, "display", None):
                try:
                    await self._display_bridge.push_to_all("skill.display", {"skill": skill_name, "display": result.display})
                except Exception as d_err:
                    logger.warning(f"Failed to push skill display to bridge: {d_err}")

            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_t) * 1000
            self.skills.record_execution(skill_name, False, duration_ms)
            logger.error(f"Skill execution error: {e}")
            return SkillResult.fail(str(e))

    async def resolve_pending_action(self, correlation_id: str, approved: bool) -> None:
        """Resolve a pending action, executing if approved and updating TrustEngine."""
        action = None
        for a in self.pending_actions:
            if a.correlation_id == correlation_id:
                action = a
                break

        if not action:
            logger.warning(f"[Gateway] Pending action not found: {correlation_id}")
            return

        self.pending_actions.remove(action)

        # Record outcome in TrustEngine
        if self._trust_engine:
            await self._trust_engine.record_outcome(
                domain="skills",
                context=action.skill_name,
                approved=approved
            )

        if approved:
            logger.info(f"[Gateway] Action approved: {action.skill_name}")
            await self.execute_skill(action.skill_name, action.params)
        else:
            logger.info(f"[Gateway] Action rejected: {action.skill_name}")

    # =========================================================================
    # Xi (Background Task Manager)
    # =========================================================================

    def _init_xi(self) -> Xi | None:
        """Initialize Xi with registered BreathTasks."""
        try:
            from .shen.inari import Inari
            from .shen.device_watchdog import DeviceWatchdog
            from .shen.saraswati import Saraswati
            from .shen.trust import TrustEngine
            from .shen.affinity import ModelAffinityTracker
            from .shen.triangulation import TriangulationTask
            from .shen.skill_approval import SkillApprovalTask
            from .shen.occam import OccamsRazorTask
            from .onboarding import InterrogatorTask

            xi = Xi()

            # Shared subsystems for BreathTasks
            trust_engine = TrustEngine()
            affinity_tracker = ModelAffinityTracker()

            # Register core BreathTasks (priority order)
            xi.register_task(Fuxi(jing=self.yi.jing, po=self.yi.po))                                # Priority 3: consolidation
            xi.register_task(Agni())                                # Priority 5: purification
            xi.register_task(TriangulationTask())                   # Priority 6: spatial learning
            xi.register_task(Inari(                                 # Priority 7: cache refresh
                trust_engine=trust_engine,
                affinity_tracker=affinity_tracker,
            ))
            xi.register_task(DeviceWatchdog())                      # Priority 8: health monitor
            xi.register_task(OccamsRazorTask(jing=self.yi.jing))    # Priority 8: causal log conflict resolver
            xi.register_task(Saraswati(trust_engine=trust_engine))  # Priority 9: skill learning
            xi.register_task(SkillApprovalTask())                   # Priority 10: skill approval check
            xi.register_task(InterrogatorTask())                    # Priority 20: background scanner

            # Register privacy, honeypot, and deception BreathTasks
            try:
                from .privacy.tasks import (
                    MetadataStripperTask,
                    HoneypotMonitor,
                    NarrativeRadarTask,
                    CanaryMonitor,
                    PhantomPersonaManager,
                    TrackerPolluter,
                    AIToolNoise,
                )
                xi.register_task(MetadataStripperTask())
                xi.register_task(HoneypotMonitor())
                xi.register_task(NarrativeRadarTask())
                xi.register_task(CanaryMonitor())
                xi.register_task(PhantomPersonaManager())
                xi.register_task(TrackerPolluter())
                xi.register_task(AIToolNoise())
            except Exception as e:
                logger.warning(f"[Gateway] Could not register privacy BreathTasks: {e}")

            # Register Skill A/B testing
            try:
                from .shen.skill_ab_test import SkillABTester
                xi.register_task(SkillABTester())
            except Exception as e:
                logger.warning(f"[Gateway] Could not register SkillABTester: {e}")

            # Store references for external access
            self._trust_engine = trust_engine
            self._affinity_tracker = affinity_tracker

            logger.info(f"[Gateway] Xi initialized with tasks: {xi.task_names}")
            return xi
        except Exception as e:
            logger.error(f"[Gateway] Failed to initialize Xi: {e}")
            return None

    async def _xi_breathe_safe(self):
        """Fire-and-forget Xi breathe with error isolation."""
        try:
            await self.xi.breathe()
        except Exception as e:
            logger.error(f"[Gateway] Xi breathe failed: {e}")



# Singleton instance
_gateway: Gateway | None = None


def get_gateway() -> Gateway:
    """Get the global Gateway instance."""
    if _gateway is None:
        raise RuntimeError("Gateway not initialized. Call init_gateway() first.")
    return _gateway


def init_gateway(
    llm_inference: LLMInferenceFunc | None = None,
    autonomy: AutonomyLevel | None = None,
    max_workers: int = 2,
    vision_enabled: bool = True,
) -> Gateway:
    """Initialize the global Gateway."""
    global _gateway
    _gateway = Gateway(
        llm_inference=llm_inference,
        autonomy_level=autonomy,
        max_workers=max_workers,
        vision_enabled=vision_enabled,
    )
    return _gateway
