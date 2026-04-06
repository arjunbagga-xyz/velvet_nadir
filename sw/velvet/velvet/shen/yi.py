"""
Yi (意): The Intent / Arbiter.

Routes cognitive focus:
- Sensory events → Po (body/reflexes)
- User text → Po macro cache first, then Hun (reasoning) if no match
- After Hun succeeds → Po learns macro for next time
"""

from loguru import logger
from velvet.config import get_config
from velvet.shen.po import Po
from velvet.shen.hun import Hun
from velvet.shen.jing import Jing


class Yi:
    """
    Yi (意): The Intent / Arbiter.

    3-tier routing:
    1. Sensory event → Po (true hardware reflex, no LLM)
    2. Po reflex match → instant skill execution (0 latency)
    3. No match → Hun reasons with LLM + tools
    """
    
    def __init__(self, start_vision_monitor: bool = True, llm_inference=None, xi=None):
        self.config = get_config()
        self.po = Po(start_vision_monitor=start_vision_monitor)
        self.hun = Hun(llm_inference=llm_inference)
        self.jing = Jing()
        self._xi = xi  # Xi background task manager (optional)

    def set_llm_inference(self, llm_inference):
        """Late-bind the LLM inference function (called by Gateway after setup)."""
        self.hun.set_llm_inference(llm_inference)

    async def on_vision_event(self, image_b64: str, score: float):
        """Pass vision event to Po (sensory → body)."""
        await self.po.on_vision_event(image_b64, score)

    async def dispatch(self, input_signal: str) -> str:
        """
        Route input to the appropriate Cognion.

        1. Try Po reflex (hard-wired patterns, 0 latency)
        2. If no match → Hun (LLM reasoning with tools)
        """
        logger.info(f"[Yi] Dispatching signal: {input_signal[:50]}...")
        
        # 1. Remember the input
        await self.jing.remember(f"User Input: {input_signal}")
        
        # 2. Try Po reflex first (instant, no LLM)
        reflex_response = await self.po.reflex(input_signal)
        if reflex_response is not None:
            logger.info("[Yi] Handled by Po (reflex)")
            await self.jing.remember(f"System Response (Po): {reflex_response}", role="assistant")
            self._record_turn(input_signal, reflex_response, routed_to="po")
            return reflex_response
        
        # 3. No reflex match → route to Hun (LLM reasoning)
        logger.info("[Yi] Routing to Hun (reasoning)")
        context_list = await self.jing.recall(input_signal)
        context_str = "\n".join(context_list) if context_list else "No relevant context."
        
        response = await self.hun.reason(context=context_str, task=input_signal)
        
        # 4. Remember the response
        await self.jing.remember(f"System Response (Hun): {response}", role="assistant")
        self._record_turn(input_signal, response, routed_to="hun")
        
        return response

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

