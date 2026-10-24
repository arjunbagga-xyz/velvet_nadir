"""
NarrativeRadar Intelligence Subsystem for Velvet Nadir.
"""

from .types import EntityType, RelationType, EntityCategory, IntelligenceEntity, IntelligenceTriple
from .config import NarrativeRadarConfig, BranchConfig
from .ingest import BaseFeed, FeedCategory, FeedMetadata, FeedItem, StandardEvent
from .correlation import (
    NarrativeCorrelationEngine,
    CorrelationResult,
    NarrativeClassification,
)
from .scorer import DemographicViralityScorer, ViralityMetric
from .radar import NarrativeRadar, DailyIntelligenceBrief

__all__ = [
    "EntityType",
    "RelationType",
    "EntityCategory",
    "IntelligenceEntity",
    "IntelligenceTriple",
    "NarrativeRadarConfig",
    "BranchConfig",
    "BaseFeed",
    "FeedCategory",
    "FeedMetadata",
    "FeedItem",
    "StandardEvent",
    "NarrativeCorrelationEngine",
    "CorrelationResult",
    "NarrativeClassification",
    "DemographicViralityScorer",
    "ViralityMetric",
    "NarrativeRadar",
    "DailyIntelligenceBrief",
]
