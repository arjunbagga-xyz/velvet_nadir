"""
Trust Engine: User Autonomy Trust.

Tracks whether the user has approved certain action domains and contexts.
Hot cache for <1ms sync reads during conversation; Jing backing for persistence.

This is NOT the device trust model (that's TrustLevel on Device).
This is about user → agent trust: "Should Velvet ask before doing X?"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


@dataclass
class TrustDecision:
    """A recorded user trust decision."""
    domain: str           # e.g. "smart_home", "calendar", "purchases"
    context: str          # e.g. "turn_off_lights", "create_event"
    approved: bool        # Did the user approve?
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.5  # 0=always ask, 1=always auto-approve


class TrustEngine:
    """
    Manages user trust decisions for agent autonomy.

    Hot cache for sync reads, Jing backing for persistence.
    Cache is refreshed by Inari BreathTask between conversations.
    """

    def __init__(self, jing=None):
        self._jing = jing
        self._cache: dict[str, TrustDecision] = {}

    def should_ask(self, domain: str, context: str = "") -> bool:
        """
        Should the agent ask the user before performing this action?

        Sync read from cache (<1ms). Returns True if we should ask,
        False if auto-approved.
        """
        key = self._cache_key(domain, context)

        # Check exact match first
        if key in self._cache:
            decision = self._cache[key]
            return not decision.approved or decision.confidence < 0.8

        # Check domain-level fallback
        domain_key = self._cache_key(domain, "")
        if domain_key in self._cache:
            decision = self._cache[domain_key]
            return not decision.approved or decision.confidence < 0.8

        # Unknown domain/context → ask by default
        return True

    async def record_outcome(self, domain: str, context: str, approved: bool):
        """
        Record a user trust decision (async write to Jing).

        Updates the hot cache immediately and persists to Jing.
        """
        key = self._cache_key(domain, context)

        # Update or create decision
        if key in self._cache:
            existing = self._cache[key]
            # Exponential moving average for confidence
            if approved:
                existing.confidence = min(1.0, existing.confidence + 0.1)
            else:
                existing.confidence = max(0.0, existing.confidence - 0.2)
            existing.approved = approved
            existing.timestamp = time.time()
        else:
            self._cache[key] = TrustDecision(
                domain=domain,
                context=context,
                approved=approved,
                confidence=0.5 if approved else 0.0,
            )

        # Persist to Jing (async)
        jing = self._get_jing()
        if jing:
            try:
                trust_text = (
                    f"Trust decision: domain={domain}, context={context}, "
                    f"approved={approved}, confidence={self._cache[key].confidence:.2f}"
                )
                await jing.remember(trust_text, role="system", metadata={
                    "source": "trust_engine",
                    "domain": domain,
                    "context": context,
                    "approved": approved,
                })
            except Exception as e:
                logger.error(f"[TrustEngine] Failed to persist to Jing: {e}")

    async def refresh_cache(self):
        """
        Refresh the hot cache from Jing.

        Called by Inari BreathTask between conversations.
        Reads all trust decisions from Jing and rebuilds the cache.
        """
        jing = self._get_jing()
        if not jing:
            return

        try:
            results = await jing.recall("trust decision", limit=50, deep=True)
            refreshed = 0
            for text in results:
                decision = self._parse_trust_text(text)
                if decision:
                    key = self._cache_key(decision.domain, decision.context)
                    self._cache[key] = decision
                    refreshed += 1

            logger.info(f"[TrustEngine] Cache refreshed: {refreshed} decisions loaded")
        except Exception as e:
            logger.error(f"[TrustEngine] Cache refresh failed: {e}")

    def get_all_decisions(self) -> list[TrustDecision]:
        """Get all cached trust decisions."""
        return list(self._cache.values())

    @staticmethod
    def _cache_key(domain: str, context: str) -> str:
        return f"{domain}:{context}" if context else domain

    @staticmethod
    def _parse_trust_text(text: str) -> TrustDecision | None:
        """Parse a trust decision from Jing memory text."""
        try:
            if "Trust decision:" not in text:
                return None
            # Extract key-value pairs
            parts = text.split("Trust decision:")[1].strip()
            pairs = {}
            for part in parts.split(", "):
                if "=" in part:
                    k, v = part.split("=", 1)
                    pairs[k.strip()] = v.strip()

            return TrustDecision(
                domain=pairs.get("domain", ""),
                context=pairs.get("context", ""),
                approved=pairs.get("approved", "").lower() == "true",
                confidence=float(pairs.get("confidence", "0.5")),
            )
        except Exception:
            return None

    def _get_jing(self):
        if self._jing is None:
            try:
                from velvet.shen.jing import Jing
                self._jing = Jing()
            except Exception:
                pass
        return self._jing
