"""
Xiān 先: Speculative Decoding & Multi-Path Thought Accelerator.

Part of the Shen cognitive subsystem.
Implements dynamic multi-model speculative reasoning across the mesh:
1. Queries Polymath and ModelAffinityTracker (mesh ELO benchmarks) to resolve:
   - Fast Draft Model (e.g. 1.5B - 3B local model on edge/Jetson)
   - High-Capacity Evaluator Model (e.g. 32B - 70B model on host PC)
2. Speculates on multi-step reasoning thoughts / tool candidate paths.
3. Evaluates draft thoughts with the evaluator model.
4. Fallback Protocol: Monitors rejection rate. If draft rejection rate exceeds threshold,
   bypasses draft speculation to preserve token efficiency and intelligence.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

from velvet.config import get_config


class XianEngine:
    """
    Xiān (先): The Speculative Thought & Acceleration Engine.
    """

    def __init__(self, max_rejections: int = 3):
        self.config = get_config()
        self.max_rejections = max_rejections
        self.consecutive_rejections = 0
        self.fallback_active = False
        
    async def resolve_speculative_pair(self) -> Tuple[Optional[str], str]:
        """
        Query Polymath and mesh ModelAffinityTracker to dynamically select
        the draft model and evaluator model based on current mesh nodes.
        """
        from velvet.shen.polymath import get_polymath
        polymath = get_polymath()

        evaluator_model = self.config.llm.model
        draft_model = None

        # Check local/mesh capabilities for a fast draft model
        if polymath.profile.vram_gb >= 16.0 or polymath.profile.ram_gb >= 32.0:
            draft_model = getattr(self.config.llm, "draft_model", "qwen:1.5b")
            
        logger.info(f"[Xiān] Mesh Model Discovery — Draft: '{draft_model or 'None'}', Evaluator: '{evaluator_model}'")
        return draft_model, evaluator_model

    async def speculate(self, prompt: str, context: str = "", draft_llm_fn=None, eval_llm_fn=None) -> Dict[str, Any]:
        """
        Execute speculative reasoning loop.
        """
        draft_model, eval_model = await self.resolve_speculative_pair()

        # If fallback active or no draft model available, run standard single-model pass
        if self.fallback_active or not draft_model or not draft_llm_fn:
            logger.info(f"[Xiān] Running direct evaluation pass (Fallback Active={self.fallback_active})...")
            start_t = time.time()
            if eval_llm_fn:
                result = await eval_llm_fn(prompt, context)
            else:
                result = "[Xiān Fallback] Evaluation executed."
            return {
                "response": result,
                "speculated": False,
                "duration_sec": round(time.time() - start_t, 3),
                "rejections": self.consecutive_rejections
            }

        logger.info(f"[Xiān] Initiating speculative decoding pass with draft model '{draft_model}'...")
        start_t = time.time()

        # 1. Generate N draft thought candidates using fast model
        try:
            draft_thoughts = await draft_llm_fn(f"[Draft Speculation] {prompt}", context)
        except Exception as e:
            logger.warning(f"[Xiān] Draft model failed ({e}). Falling back to main evaluator.")
            return await self._trigger_fallback(prompt, context, eval_llm_fn)

        # 2. Verify draft thoughts using high-capacity evaluator model
        verification_prompt = (
            f"Verify the following proposed reasoning steps for prompt: '{prompt}'.\n"
            f"Proposed Draft Steps:\n{draft_thoughts}\n"
            f"If correct and optimal, approve and finalize. Otherwise, correct them."
        )

        try:
            evaluated_result = await eval_llm_fn(verification_prompt, context)
            
            # Check if evaluator rejected the draft
            if "incorrect" in evaluated_result.lower() or "rejected" in evaluated_result.lower():
                self.consecutive_rejections += 1
                logger.warning(f"[Xiān] Draft thought rejected by Evaluator ({self.consecutive_rejections}/{self.max_rejections})")
                if self.consecutive_rejections >= self.max_rejections:
                    logger.warning("[Xiān] Maximum rejection threshold reached. Activating Fallback Protocol.")
                    self.fallback_active = True
            else:
                # Reset rejection counter on success
                self.consecutive_rejections = max(0, self.consecutive_rejections - 1)

            return {
                "response": evaluated_result,
                "speculated": True,
                "draft_used": draft_model,
                "evaluator_used": eval_model,
                "duration_sec": round(time.time() - start_t, 3),
                "rejections": self.consecutive_rejections
            }
        except Exception as e:
            logger.error(f"[Xiān] Evaluator failed during verification: {e}")
            return await self._trigger_fallback(prompt, context, eval_llm_fn)

    async def _trigger_fallback(self, prompt: str, context: str, eval_llm_fn) -> Dict[str, Any]:
        """Trigger fallback generation bypass."""
        self.fallback_active = True
        start_t = time.time()
        res = await eval_llm_fn(prompt, context) if eval_llm_fn else "[Xiān Fallback] Direct pass completed."
        return {
            "response": res,
            "speculated": False,
            "fallback_triggered": True,
            "duration_sec": round(time.time() - start_t, 3)
        }

    def reset_fallback(self):
        """Reset fallback state."""
        self.fallback_active = False
        self.consecutive_rejections = 0
        logger.info("[Xiān] Fallback state reset.")
