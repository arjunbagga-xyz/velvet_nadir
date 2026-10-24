"""
Ingest Framework for NarrativeRadar: BaseFeed lifecycle and standard event schemas.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class FeedCategory(Enum):
    SOCIAL = "social"
    PHYSICAL = "physical"


@dataclass
class FeedMetadata:
    name: str
    category: FeedCategory
    update_frequency_seconds: float
    description: str = ""
    authoritative: bool = True
    requires_auth: bool = False


@dataclass
class FeedItem:
    feed_name: str
    item_id: str
    title: str
    content: str
    author: str = ""
    timestamp: float = field(default_factory=time.time)
    url: str = ""
    tags: List[str] = field(default_factory=list)
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StandardEvent:
    event_id: str
    source_feed: str
    event_type: str  # e.g., "earthquake", "fire", "airspace", "maritime", "launch", "weather"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    magnitude: Optional[float] = None
    severity: str = "INFO"  # INFO, WARNING, CRITICAL
    description: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseFeed(ABC):
    """
    Modular lifecycle contract for all social and physical data feeds.
    Every feed must cleanly mount, poll, interpolate into standard events, and unmount.
    """

    def __init__(self):
        self.is_mounted: bool = False

    @abstractmethod
    async def mount(self) -> None:
        """Establish connections, websockets, or verify authentication."""
        ...

    @abstractmethod
    async def poll(self) -> List[FeedItem]:
        """Fetch raw data items from the feed source."""
        ...

    @abstractmethod
    async def interpolate(self, raw_data: Any) -> List[StandardEvent]:
        """Translate feed-specific records into normalized StandardEvent instances."""
        ...

    @abstractmethod
    async def unmount(self) -> None:
        """Tear down connections, cancel polling tasks, close handles."""
        ...

    @abstractmethod
    def get_metadata(self) -> FeedMetadata:
        """Return feed configuration metadata."""
        ...
