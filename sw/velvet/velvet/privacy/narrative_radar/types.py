"""
NarrativeRadar Intelligence Graph Type System.
Defines 17 entity types and 13 relation types mapped directly to MemPalace KnowledgeGraph.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class EntityCategory(Enum):
    POWER = "power"
    AMPLIFIERS = "amplifiers"
    DEMOGRAPHICS = "demographics"
    NARRATIVE = "narrative"


class EntityType(Enum):
    # Power (Tier 1)
    GOVERNMENT = "government"
    INSTITUTION = "institution"
    CORPORATION = "corporation"
    PRIVATE_EQUITY = "private_equity"
    SHADOW_NETWORK = "shadow_network"
    THINK_TANK = "think_tank"
    MEDIA_OUTLET = "media_outlet"

    # Amplifiers (Tier 2)
    POLITICAL_LEADER = "political_leader"
    EXECUTIVE = "executive"
    INFLUENCER = "influencer"
    ORGANIZATION = "organization"

    # Demographics (Tier 3)
    DEMOGRAPHIC = "demographic"
    COMMUNITY = "community"
    GEOGRAPHY = "geography"

    # Narrative & Event
    NARRATIVE = "narrative"
    EVENT = "event"
    CAMPAIGN = "campaign"

    @property
    def category(self) -> EntityCategory:
        power_types = {
            EntityType.GOVERNMENT, EntityType.INSTITUTION, EntityType.CORPORATION,
            EntityType.PRIVATE_EQUITY, EntityType.SHADOW_NETWORK, EntityType.THINK_TANK,
            EntityType.MEDIA_OUTLET
        }
        amplifier_types = {
            EntityType.POLITICAL_LEADER, EntityType.EXECUTIVE,
            EntityType.INFLUENCER, EntityType.ORGANIZATION
        }
        demographic_types = {
            EntityType.DEMOGRAPHIC, EntityType.COMMUNITY, EntityType.GEOGRAPHY
        }
        if self in power_types:
            return EntityCategory.POWER
        elif self in amplifier_types:
            return EntityCategory.AMPLIFIERS
        elif self in demographic_types:
            return EntityCategory.DEMOGRAPHICS
        return EntityCategory.NARRATIVE


class RelationType(Enum):
    # Power relations
    FUNDS = "funds"
    OWNS = "owns"
    BOARD_MEMBER_OF = "board_member_of"
    LOBBIES = "lobbies"
    INFLUENCES = "influences"

    # Narrative relations
    PUSHES = "pushes"
    AMPLIFIES = "amplifies"
    ORIGINATES = "originates"
    BENEFITS_FROM = "benefits_from"
    OPPOSES = "opposes"

    # Propagation relations
    PENETRATES = "penetrates"
    TRICKLES_TO = "trickles_to"

    # Incentive
    INCENTIVE = "incentive"


@dataclass
class IntelligenceEntity:
    name: str
    entity_type: EntityType
    branch: str = "general"
    properties: Dict[str, Any] = field(default_factory=dict)
    first_seen: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type.value,
            "category": self.entity_type.category.value,
            "branch": self.branch,
            "properties": self.properties,
            "first_seen": self.first_seen,
            "last_updated": self.last_updated,
        }


@dataclass
class IntelligenceTriple:
    subject: str
    relation: RelationType
    object: str
    weight: float = 1.0
    valid_from: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "relation": self.relation.value,
            "object": self.object,
            "weight": self.weight,
            "valid_from": self.valid_from,
            "properties": self.properties,
        }
