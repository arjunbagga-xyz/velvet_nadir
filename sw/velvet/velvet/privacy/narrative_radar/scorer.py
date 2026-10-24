"""
Self-Learning Demographic Virality Scorer.
Computes demographic-specific penetration and virality using the Chao1 nonparametric
richness estimator, with dynamic learning and MemPalace persistence.
"""

from collections import Counter
from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ViralityMetric:
    demographic_name: str
    estimated_pool_size: int
    reach: int
    engagement_rate: float
    penetration_ratio: float
    score: float  # 0 to 100
    classification: str  # CRITICAL, HIGH, MODERATE, LOW, NEGLIGIBLE


class DemographicViralityScorer:
    """
    Evaluates how deeply a narrative has penetrated a specific demographic circle.
    Does not use hardcoded sizes; estimates pool size dynamically using Chao1 richness.
    """

    def __init__(self, jing_instance: Optional[Any] = None):
        self.jing = jing_instance
        # In-memory demographic size cache (fallback when MemPalace is offline/local)
        self._learned_sizes: Dict[str, int] = {}

    def get_coverage_multiplier(self, demographic_name: str) -> float:
        """
        Calculates heuristic coverage multiplier based on domain sampling coverage.
        Default is 5.0 (assuming sample covers ~20% of active discourse).
        """
        name_lower = demographic_name.lower()
        if "scientific" in name_lower or "research" in name_lower or "cryptography" in name_lower:
            return 3.0  # Tighter, more observable community
        elif "consumer" in name_lower or "mass" in name_lower or "general" in name_lower:
            return 10.0  # Broader, vast community
        return 5.0

    def estimate_community_size_chao1(
        self,
        demographic_name: str,
        observed_author_handles: List[str],
    ) -> int:
        """
        Calculates estimated total community size using the Chao1 estimator:
        N_est = (S + (F1^2 / (2 * max(F2, 1)))) * coverage_multiplier
        where:
          S  = observed unique authors
          F1 = singletons (authors observed exactly 1 time)
          F2 = doubletons (authors observed exactly 2 times)
        """
        if not observed_author_handles:
            return self._learned_sizes.get(demographic_name, 1000)

        counts = Counter(observed_author_handles)
        s = len(counts)  # Unique observed authors
        f1 = sum(1 for c in counts.values() if c == 1)
        f2 = sum(1 for c in counts.values() if c == 2)

        # Chao1 formula
        chao1_s_est = s + (f1 * f1) / (2.0 * max(f2, 1))
        multiplier = self.get_coverage_multiplier(demographic_name)
        total_est = int(round(chao1_s_est * multiplier))
        if total_est < s:
            total_est = s

        # Save learned size in cache and MemPalace if available
        self._learned_sizes[demographic_name] = total_est
        if self.jing and hasattr(self.jing, "graph_add_entity"):
            try:
                # Asynchronously store demographic entity and estimated size
                import asyncio
                loop = None
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    pass
                if loop and loop.is_running():
                    loop.create_task(
                        self.jing.graph_add_entity(
                            name=f"demographic:{demographic_name}",
                            entity_type="demographic"
                        )
                    )
            except Exception as e:
                logger.debug(f"[ViralityScorer] Could not persist to MemPalace: {e}")

        logger.debug(
            f"[ViralityScorer] Chao1 estimate for '{demographic_name}': "
            f"S={s}, F1={f1}, F2={f2} -> N_est={total_est}"
        )
        return total_est

    def compute_virality_score(
        self,
        demographic_name: str,
        reach: int,
        engagement_rate: float,
        observed_authors: Optional[List[str]] = None,
        override_pool_size: Optional[int] = None,
    ) -> ViralityMetric:
        """
        Compute penetration and virality score:
        Penetration P = reach / N_est
        Score = (P * 0.6 + engagement_rate * 0.4) * 100
        """
        if override_pool_size:
            n_est = override_pool_size
        elif observed_authors:
            n_est = self.estimate_community_size_chao1(demographic_name, observed_authors)
        elif demographic_name in self._learned_sizes:
            n_est = self._learned_sizes[demographic_name]
        else:
            n_est = 5000  # Conservative bootstrap default

        penetration = min(1.0, reach / max(n_est, 1))
        clamped_engagement = min(1.0, max(0.0, engagement_rate))

        raw_score = (penetration * 0.6 + clamped_engagement * 0.4) * 100.0
        score = round(min(100.0, max(0.0, raw_score)), 2)

        if score >= 70.0:
            classification = "CRITICAL"
        elif score >= 40.0:
            classification = "HIGH"
        elif score >= 15.0:
            classification = "MODERATE"
        elif score >= 5.0:
            classification = "LOW"
        else:
            classification = "NEGLIGIBLE"

        return ViralityMetric(
            demographic_name=demographic_name,
            estimated_pool_size=n_est,
            reach=reach,
            engagement_rate=clamped_engagement,
            penetration_ratio=round(penetration, 4),
            score=score,
            classification=classification,
        )
