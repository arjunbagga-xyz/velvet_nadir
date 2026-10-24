"""
Configuration and quota management for NarrativeRadar intelligence branches.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BranchConfig:
    name: str
    description: str
    enabled: bool = True
    sources: List[str] = field(default_factory=list)
    mesh_threat_check: bool = False
    max_entities: int = 5000
    max_triples: int = 20000
    retention_days: int = 90


@dataclass
class NarrativeRadarConfig:
    """
    Selective tracking configuration to avoid early storage bloat.
    Starts with 3 active branches with strict entity and triple quotas.
    """
    branches: Dict[str, BranchConfig] = field(default_factory=dict)
    global_max_entities: int = 25000
    global_max_triples: int = 100000
    retention_days: int = 90
    poll_interval_hours: float = 24.0

    @classmethod
    def default(cls) -> "NarrativeRadarConfig":
        cfg = cls()
        cfg.branches = {
            "AI Regulation & Safety": BranchConfig(
                name="AI Regulation & Safety",
                description="Global governance, AI safety frameworks, copyright and export controls.",
                enabled=True,
                sources=["techcrunch", "arxiv", "reddit_ml"],
                mesh_threat_check=False,
                max_entities=5000,
                max_triples=20000,
            ),
            "Cybersecurity Threats": BranchConfig(
                name="Cybersecurity Threats",
                description="Critical zero-days, supply-chain exploits, hardware CVEs affecting mesh.",
                enabled=True,
                sources=["krebsonsecurity", "hackernews", "telegram_cybersec"],
                mesh_threat_check=True,
                max_entities=5000,
                max_triples=20000,
            ),
            "Geopolitical Shifts": BranchConfig(
                name="Geopolitical Shifts",
                description="Sanctions, international statecraft, critical infrastructure and supply chains.",
                enabled=True,
                sources=["gdelt", "reuters", "foreignaffairs"],
                mesh_threat_check=False,
                max_entities=5000,
                max_triples=20000,
            ),
        }
        return cfg

    def get_active_branches(self) -> List[BranchConfig]:
        """Return list of currently enabled branches."""
        return [b for b in self.branches.values() if b.enabled]

    def is_branch_enabled(self, branch_name: str) -> bool:
        """Check if branch is enabled."""
        branch = self.branches.get(branch_name)
        return bool(branch and branch.enabled)

    def toggle_branch(self, branch_name: str, enabled: bool) -> None:
        """Enable or disable a specific branch."""
        if branch_name in self.branches:
            self.branches[branch_name].enabled = enabled
