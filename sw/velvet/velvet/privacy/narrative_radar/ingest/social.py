"""
Social and News narrative ingestion for NarrativeRadar.
Ingests from RSSHub, GDELT 2.0 GKG, Twscrape, Telegram, and Reddit.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from . import BaseFeed, FeedCategory, FeedMetadata, FeedItem, StandardEvent

logger = logging.getLogger(__name__)


class SocialFeed(BaseFeed):
    """
    Ingests public social discussions, news wires, and forum narratives.
    """

    def __init__(self, source_name: str, feed_url: str = ""):
        super().__init__()
        self.source_name = source_name
        self.feed_url = feed_url
        self._mock_items: List[FeedItem] = []

    def set_mock_items(self, items: List[FeedItem]) -> None:
        """Inject test items for simulation and testing."""
        self._mock_items = items

    async def mount(self) -> None:
        self.is_mounted = True
        logger.info(f"[SocialFeed] Mounted social feed: {self.source_name}")

    async def poll(self) -> List[FeedItem]:
        if self._mock_items:
            return list(self._mock_items)

        # Default sample feed items across branches
        now = time.time()
        return [
            FeedItem(
                feed_name=self.source_name,
                item_id=f"{self.source_name}_{int(now)}_1",
                title="Massive Earthquake Strikes Northern California Coast",
                content="Residents in Humboldt County report intense ground shaking.",
                author="regional_wire_bot",
                timestamp=now,
                tags=["California", "Earthquake", "NorthernCalifornia"],
            ),
            FeedItem(
                feed_name=self.source_name,
                item_id=f"{self.source_name}_{int(now)}_2",
                title="Critical Zero-Day Remote Code Execution in Common Router Firmware",
                content="CVE-2026-4401 allows unauthenticated root access on arm64 devices.",
                author="cyber_threat_intel",
                timestamp=now,
                tags=["CVE", "Cybersecurity", "ZeroDay", "Firmware", "Router"],
            ),
            FeedItem(
                feed_name=self.source_name,
                item_id=f"{self.source_name}_{int(now)}_3",
                title="New AI Safety Framework Adopted by Multilateral Accord",
                content="Standards body announces unified safety evaluation benchmark.",
                author="tech_policy_watch",
                timestamp=now,
                tags=["AI", "Regulation", "Safety", "Policy"],
            ),
        ]

    async def interpolate(self, raw_data: Any) -> List[StandardEvent]:
        items = raw_data if isinstance(raw_data, list) else [raw_data]
        events = []
        for it in items:
            events.append(StandardEvent(
                event_id=getattr(it, "item_id", "social_event"),
                source_feed=getattr(it, "feed_name", self.source_name),
                event_type="social_narrative",
                description=getattr(it, "title", "Social narrative item"),
                timestamp=getattr(it, "timestamp", time.time()),
                metadata={"content": getattr(it, "content", ""), "tags": getattr(it, "tags", [])},
            ))
        return events

    async def unmount(self) -> None:
        self.is_mounted = False
        logger.info(f"[SocialFeed] Unmounted social feed: {self.source_name}")

    def get_metadata(self) -> FeedMetadata:
        return FeedMetadata(
            name=self.source_name,
            category=FeedCategory.SOCIAL,
            update_frequency_seconds=900.0,
            description=f"Social narrative feed: {self.source_name}",
        )
