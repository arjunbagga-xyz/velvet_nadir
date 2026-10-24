"""
Yi (意): The Intent / Arbiter.

Routes cognitive focus using a state-graph router:
- Sensory events → Po (body/reflexes)
- User text → Po macro cache first, then Hun (reasoning) if no match
- Reverse Escalation: Po or Skills emitting ReasoningDemand escalation → Hun
- Modality Scoring Engine: calculates UI_Score (D + V*1.5 + M*2 + S) to determine output modality
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Dict, List
from loguru import logger
from velvet.config import get_config
from velvet.shen.po import Po
from velvet.shen.hun import Hun
from velvet.shen.jing import Jing


class ModalityLevel(Enum):
    ZERO_UI = 0       # Ambient/Audio default
    MICRO_UI = 1      # Ephemeral toast/notification
    WIDGET_UI = 2     # Bounded interactive floating tool
    MACRO_UI = 3      # Dynamic workspace takeover


@dataclass
class DispatchState:
    input_signal: str
    context: str = ""
    route: str = "undecided"
    response: str = ""
    modality: ModalityLevel = ModalityLevel.ZERO_UI
    ui_score: float = 0.0
    skill_used: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    reasoning_demanded: bool = False


@dataclass
class DispatchResult:
    response: str
    modality: ModalityLevel
    ui_score: float
    skill_used: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    routed_to: str = "hun"

    def __str__(self) -> str:
        """Backwards compatibility for callers expecting a raw string."""
        return self.response


class Yi:
    """
    Yi (意): The Intent / Arbiter.

    SOTA State Router & Cognitive Dispatcher.
    """
    
    def __init__(self, start_vision_monitor: bool = True, llm_inference=None, xi=None):
        self.config = get_config()
        self.po = Po(start_vision_monitor=start_vision_monitor)
        self.hun = Hun(llm_inference=llm_inference)
        self.jing = Jing()
        self._xi = xi  # Xi background task manager (optional)
        self._recent_responses: list[str] = []

    def set_llm_inference(self, llm_inference):
        """Late-bind the LLM inference function (called by Gateway after setup)."""
        self.hun.set_llm_inference(llm_inference)

    async def on_vision_event(self, image_b64: str, score: float):
        """Pass vision event to Po (sensory → body)."""
        await self.po.on_vision_event(image_b64, score)

    async def dispatch(self, input_signal: str) -> DispatchResult:
        """
        Dynamic State Router dispatch loop.

        Edges:
        1. Input -> Jing Memory Log
        2. Try Po Reflex (instant 0 latency match)
        3. Reverse Escalation check (Po/Skill demands reasoning) -> Hun
        4. No reflex -> Hun (Deep LLM reasoning)
        5. Score Modality -> determine ZERO/MICRO/WIDGET/MACRO UI
        6. Record turn to Xi & return DispatchResult
        """
        logger.info(f"[Yi] Dispatching signal: {input_signal[:50]}...")
        state = DispatchState(input_signal=input_signal)

        # 1. Remember input
        await self.jing.remember(f"User Input: {input_signal}")

        # 2. Try Po reflex first
        state = await self._try_po_reflex(state)
        if state.route == "po" and not state.reasoning_demanded:
            state = self._score_modality(state)
            await self.jing.remember(f"System Response (Po): {state.response}", role="assistant")
            self._record_turn(input_signal, state.response, routed_to="po", skill_used=state.skill_used, params=state.params)
            return DispatchResult(
                response=state.response,
                modality=state.modality,
                ui_score=state.ui_score,
                skill_used=state.skill_used,
                params=state.params,
                routed_to="po"
            )

        # 3. Route to Hun (Reasoning)
        state = await self._route_to_hun(state)

        # 4. Score Modality Level
        state = self._score_modality(state)

        # 5. Remember System Response
        await self.jing.remember(f"System Response (Hun): {state.response}", role="assistant")
        self._record_turn(input_signal, state.response, routed_to="hun", skill_used=state.skill_used, params=state.params)

        return DispatchResult(
            response=state.response,
            modality=state.modality,
            ui_score=state.ui_score,
            skill_used=state.skill_used,
            params=state.params,
            routed_to="hun"
        )

    async def _try_po_reflex(self, state: DispatchState) -> DispatchState:
        """Check Po fast reflex match."""
        try:
            reflex_response = await self.po.reflex(state.input_signal)
            if reflex_response is not None:
                if reflex_response == "ESCALATE":
                    state.reasoning_demanded = True
                    state.route = "po_escalated"
                else:
                    state.response = reflex_response
                    state.route = "po"
        except Exception as e:
            logger.error(f"[Yi] Error in Po reflex: {e}")
            state.reasoning_demanded = True
        return state

    def _check_repetition(self, response: str) -> bool:
        """
        Macro repetition detector across recent turns using SequenceMatcher.
        Triggers if response is >90% identical to any of the last 5 turns.
        """
        if not response or not self._recent_responses:
            return False
        import difflib
        resp_clean = response.strip()
        for past in self._recent_responses[-5:]:
            ratio = difflib.SequenceMatcher(None, past.strip(), resp_clean).ratio()
            if ratio > 0.90:
                logger.warning(
                    f"[Yi] Macro repetition detected ({ratio:.2%}) matching past turn. Engaging repetition break."
                )
                return True
        return False

    async def _route_to_hun(self, state: DispatchState) -> DispatchState:
        """Route input and recall context to Hun."""
        logger.info(f"[Yi] Routing to Hun (reasoning, escalation={state.reasoning_demanded})")
        context_list = await self.jing.recall(state.input_signal)
        context_str = "\n".join(context_list) if context_list else "No relevant context."
        
        response = await self.hun.reason(context=context_str, task=state.input_signal)
        if self._check_repetition(response):
            logger.info("[Yi] Breaking macro repetition loop with directive")
            retry_task = (
                f"{state.input_signal}\n"
                "[System: Do not repeat your previous phrasing. Provide a direct, alternative response.]"
            )
            response = await self.hun.reason(context=context_str, task=retry_task)

        self._recent_responses.append(response)
        if len(self._recent_responses) > 20:
            self._recent_responses.pop(0)

        state.response = response
        state.route = "hun"
        return state

    def _score_modality(self, state: DispatchState) -> DispatchState:
        """
        Modality Routing Engine.
        Formula: UI_Score = D + (V * 1.5) + (M * 2) + S
        """
        text = (state.input_signal + " " + state.response).lower()

        # Heuristic scoring based on intent and content patterns
        D = 0  # Spatial/Data complexity
        V = 0  # Visual necessity
        M = 0  # Direct manipulation requirement
        S = 0  # Safety / High-stakes confirmation

        # Media controls (timeline, video, audio)
        if any(w in text for w in ["play", "video", "audio", "timeline", "scrub", "stream"]):
            D += 2; V += 2; M += 3

        # 3D / Spatial / Mesh manipulation
        if any(w in text for w in ["3d", "model", "canvas", "rotate", "inspect", "mesh", "render"]):
            D += 3; V += 3; M += 3

        # File management / Tree / Explorer
        if any(w in text for w in ["file", "files", "folder", "directory", "explorer", "tree"]):
            D += 2; V += 1; M += 2

        # Comparison / Charts / Tables
        if any(w in text for w in ["chart", "table", "compare", "dashboard", "graph"]):
            D += 2; V += 2; M += 1

        # Destructive / Security / Autonomy approval
        if any(w in text for w in ["approve", "permission", "confirm", "delete", "format"]):
            S += 2; M += 1

        # Simple commands (lights, status, time) -> zero UI
        if any(w in text for w in ["time", "turn on", "turn off", "status", "weather"]):
            D = 0; V = 0; M = 0

        score = D + (V * 1.5) + (M * 2) + S
        state.ui_score = score

        if score < 4.0:
            state.modality = ModalityLevel.ZERO_UI
        elif 4.0 <= score < 7.0:
            state.modality = ModalityLevel.MICRO_UI
        elif 7.0 <= score < 11.0:
            state.modality = ModalityLevel.WIDGET_UI
        else:
            state.modality = ModalityLevel.MACRO_UI

        logger.debug(f"[Yi] Scored modality for '{state.input_signal[:30]}': score={score:.1f} -> {state.modality.name}")
        return state

    def _record_turn(self, user_input: str, response: str,
                     routed_to: str = "", skill_used: str | None = None,
                     params: dict | None = None):
        """Record a conversation turn to Xi journal (if Xi is available)."""
        if self._xi is None:
            return
        try:
            from velvet.shen.xi import ConversationTurn
            turn = ConversationTurn(
                user_input=user_input,
                response=response,
                routed_to=routed_to,
                skill_used=skill_used,
                params=params or {},
            )
            self._xi.record(turn)
        except Exception as e:
            logger.error(f"[Yi] Failed to record turn to Xi: {e}")

