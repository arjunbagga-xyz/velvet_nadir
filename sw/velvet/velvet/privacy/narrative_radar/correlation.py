"""
Physical Event <-> Narrative Correlation & Mesh Threat Engine.
Correlates social narrative velocity spikes (>3 sigma) against ground-truth physical telemetry,
detects manufactured astroturf campaigns, and checks for mesh hardware exposure.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Any, Dict, List, Optional, Set

from .ingest import StandardEvent

logger = logging.getLogger(__name__)


class NarrativeClassification(Enum):
    ORGANIC_EVENT = "ORGANIC_EVENT"
    MANUFACTURED_ASTROTURF = "MANUFACTURED_ASTROTURF"
    UNCORRELATED_DISCUSSION = "UNCORRELATED_DISCUSSION"


@dataclass
class CorrelationResult:
    narrative_id: str
    classification: NarrativeClassification
    confidence: float
    matched_physical_event: Optional[StandardEvent] = None
    astroturf_details: Optional[Dict[str, Any]] = None
    mesh_threat: bool = False
    affected_mesh_devices: List[str] = field(default_factory=list)
    alert_message: str = ""
    timestamp: float = field(default_factory=time.time)


class NarrativeCorrelationEngine:
    """
    Correlates social narrative spikes against physical feeds (USGS, FIRMS, AISStream, OpenSky, etc.)
    and detects coordinated astroturf manipulation or mesh vulnerabilities.
    """

    def __init__(self, hardware_registry: Optional[Any] = None):
        self.hardware_registry = hardware_registry

    def correlate(
        self,
        narrative_id: str,
        narrative_title: str,
        thematic_tags: List[str],
        velocity_sigma: float,
        channel_burst_timestamps: List[float],
        physical_events: List[StandardEvent],
        spike_timestamp: Optional[float] = None,
        mesh_threat_check: bool = False,
    ) -> CorrelationResult:
        """
        Evaluate a narrative against physical telemetry and burst characteristics.
        
        Args:
            narrative_id: ID of the narrative spike.
            narrative_title: Title or summary of narrative.
            thematic_tags: Extracted spatial and topical keywords (e.g. ['California', 'Earthquake']).
            velocity_sigma: Growth rate standard deviations (>3.0 = velocity spike).
            channel_burst_timestamps: Timestamps of distinct social channels posting about the topic.
            physical_events: Physical events from USGS, FIRMS, OpenSky, etc.
            spike_timestamp: Time of the detected narrative spike.
            mesh_threat_check: Whether to verify if CVE/exploit tags affect local mesh hardware.
        """
        ts = spike_timestamp or time.time()
        time_window_sec = 6 * 3600.0  # +/- 6 hours
        normalized_tags = {t.lower() for t in thematic_tags}

        # 1. Physical Feed Correlation
        matched_physical: Optional[StandardEvent] = None
        for pe in physical_events:
            # Check within 6-hour window
            if abs(pe.timestamp - ts) <= time_window_sec:
                # Match tags against physical event description and metadata
                pe_text = f"{pe.event_type} {pe.description} {' '.join(str(v) for v in pe.metadata.values())}".lower()
                matches = [t for t in normalized_tags if t in pe_text]
                if len(matches) >= 2 or (len(matches) >= 1 and len(normalized_tags) == 1):
                    matched_physical = pe
                    break

        # 2. Astroturf Burst Check
        # 3+ coordinated channels posting within 8 minutes (480s) of each other
        is_astroturf_burst = False
        astroturf_info = None
        if len(channel_burst_timestamps) >= 3:
            sorted_times = sorted(channel_burst_timestamps)
            # Check sliding window of 3 channels
            for i in range(len(sorted_times) - 2):
                span = sorted_times[i + 2] - sorted_times[i]
                if span <= 480.0:  # 8 minutes
                    is_astroturf_burst = True
                    astroturf_info = {
                        "coordinated_channels_count": len(sorted_times),
                        "window_span_seconds": span,
                        "flag": "synchronized_burst_without_physical_anchor",
                    }
                    break

        # 3. Correlation Decision
        if matched_physical:
            classification = NarrativeClassification.ORGANIC_EVENT
            confidence = 0.95
            alert_msg = f"Confirmed organic event matching physical telemetry: {matched_physical.description}"
        elif is_astroturf_burst:
            classification = NarrativeClassification.MANUFACTURED_ASTROTURF
            confidence = 0.85
            alert_msg = f"⚠️ ANOMALY ALERT: Coordinated astroturf narrative detected! 3+ channels burst within 8 minutes without physical confirmation."
        else:
            classification = NarrativeClassification.UNCORRELATED_DISCUSSION
            confidence = 0.60
            alert_msg = "Uncorrelated social narrative or organic discussion."

        # 4. Mesh Threat Check
        mesh_threat = False
        affected_devices = []
        if mesh_threat_check and self.hardware_registry:
            threat_keywords = {"cve", "zero-day", "zeroday", "exploit", "firmware", "vulnerability", "router", "rce"}
            if any(k in normalized_tags or k in narrative_title.lower() for k in threat_keywords):
                try:
                    devices = self.hardware_registry.get_all_devices()
                    for dev in devices:
                        dev_hardware_cpu = getattr(dev.hardware, "cpu", "") or getattr(dev.hardware, "cpu_arch", "")
                        dev_software_os = getattr(dev.software, "os", "") or getattr(dev.software, "os_name", "")
                        dev_info = (
                            f"{dev.name} {dev_hardware_cpu} {dev_software_os} "
                            f"{dev.software.os_version} {' '.join(dev.metadata.keys())} "
                            f"{' '.join(str(v) for v in dev.metadata.values())}"
                        ).lower()
                        # Cross-reference tags with device hardware signatures
                        matched_dev_tags = [t for t in normalized_tags if len(t) > 2 and t in dev_info]
                        if matched_dev_tags:
                            mesh_threat = True
                            affected_devices.append(dev.name)

                    if mesh_threat:
                        alert_msg = f"⚠️ SECURITY ALERT: Affects mesh devices! ({', '.join(affected_devices)}) - {alert_msg}"
                except Exception as e:
                    logger.error(f"[NarrativeCorrelation] Mesh threat check failed: {e}")

        logger.info(
            f"[NarrativeCorrelation] Narrative '{narrative_id}' -> {classification.value} "
            f"(Conf: {confidence:.2f}, MeshThreat: {mesh_threat})"
        )

        return CorrelationResult(
            narrative_id=narrative_id,
            classification=classification,
            confidence=confidence,
            matched_physical_event=matched_physical,
            astroturf_details=astroturf_info,
            mesh_threat=mesh_threat,
            affected_mesh_devices=affected_devices,
            alert_message=alert_msg,
            timestamp=ts,
        )
