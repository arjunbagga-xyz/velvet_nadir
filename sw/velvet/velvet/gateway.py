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

        # Queue and workers
        self._queue: asyncio.PriorityQueue[GatewayRequest] = asyncio.PriorityQueue()
        self._workers: list[asyncio.Task] = []
        self._max_workers = max_workers
        self._seq_counter = 0  # Monotonic counter for tie-breaking

        # Cancel support — tracks active request cancel events
        self._active_cancels: list[asyncio.Event] = []

        # LLM timeout from config
        self._llm_timeout = get_config().llm.timeout_sec

        # TTS serialization lock — prevents overlapping speech
        self._tts_lock = asyncio.Lock()

        # Project Shen: Cognitive Core
        self.agent_orchestrator = AgentOrchestrator()
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
            await self.execute_skill(skill_name, params)

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
        if not skill_name:
            logger.warning("Received skill request with no skill name")
            return
        logger.info(f"Skill request via fabric: {skill_name} (source={msg.payload.get('source', 'unknown')})")
        self._enqueue(GatewayRequest(
            priority=Priority.HIGH,
            request_type="skill",
            payload={"skill": skill_name, "params": params},
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
            await self._process_input(text)

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

    def _enqueue(self, request: GatewayRequest) -> None:
        """Add a request to the priority queue with a monotonic sequence number."""
        self._seq_counter += 1
        request._seq = self._seq_counter
        self._queue.put_nowait(request)

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

            # Trigger Xi breathe at conversation boundary
            if self.xi:
                asyncio.create_task(self._xi_breathe_safe())



    async def _handle_llm_response(self, response: str) -> None:
        """
        Handle LLM response, parsing and executing tool calls.

        Uses tool_parsing module for extraction.
        """
        tool_calls = extract_tool_calls(response)

        if not tool_calls:
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
                self.context.add_conversation_message("assistant", text_response)
                await self._speak(text_response)

    # =========================================================================
    # TTS (serialized via lock)
    # =========================================================================

    async def _speak(self, text: str) -> None:
        """Send text to TTS for speaking. Serialized and awaits completion."""
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

    async def execute_skill(self, skill_name: str, params: dict[str, Any]) -> SkillResult:
        """Execute a skill by name."""
        skill = self.skills.get(skill_name)
        if not skill:
            return SkillResult.fail(f"Unknown skill: {skill_name}")

        defn = skill.definition

        # Check autonomy level
        if defn.autonomy_required.value > self.autonomy_level.value:
            return SkillResult.fail(
                f"Skill {skill_name} requires autonomy level {defn.autonomy_required.name}"
            )

        # Validate parameters
        valid, error = await skill.validate_params(**params)
        if not valid:
            return SkillResult.fail(error or "Invalid parameters")

        # Execute
        try:
            logger.info(f"Executing skill: {skill_name}")
            result = await skill.execute(**params)

            if result.speak:
                await self._speak(result.speak)

            return result
        except Exception as e:
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
            xi.register_task(Saraswati(trust_engine=trust_engine))  # Priority 9: skill learning
            xi.register_task(SkillApprovalTask())                   # Priority 10: skill approval check

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
