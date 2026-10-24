"""
Unit and integration tests for Velvet Nadir Phase 5:
NarrativeRadar Intelligence Subsystem: Feeds, Correlation, Chao1 Demographic Virality,
and MemPalace Intelligence Graph.
"""

import asyncio
import time
import pytest

from velvet.privacy.narrative_radar.types import EntityType, RelationType, EntityCategory
from velvet.privacy.narrative_radar.config import NarrativeRadarConfig
from velvet.privacy.narrative_radar.ingest.physical import (
    USGSFeed, FIRMSFeed, OpenSkyFeed, AISStreamFeed,
    CelesTrakFeed, TeleGeographyFeed, LaunchLibraryFeed, NOAAFeed,
)
from velvet.privacy.narrative_radar.ingest.social import SocialFeed
from velvet.privacy.narrative_radar.correlation import (
    NarrativeCorrelationEngine,
    NarrativeClassification,
)
from velvet.privacy.narrative_radar.scorer import DemographicViralityScorer
from velvet.privacy.narrative_radar.radar import NarrativeRadar
from velvet.devices import HardwareRegistry, Device, DeviceType, DeviceRole, TrustLevel, HardwareSpecs, SoftwareSpecs


@pytest.mark.asyncio
async def test_all_8_physical_feeds_lifecycle():
    """Verify that all 8 God's Eye View physical feeds mount, poll, interpolate, and unmount."""
    feeds = [
        USGSFeed(),
        FIRMSFeed(),
        OpenSkyFeed(),
        AISStreamFeed(),
        CelesTrakFeed(),
        TeleGeographyFeed(),
        LaunchLibraryFeed(),
        NOAAFeed(),
    ]

    for feed in feeds:
        meta = feed.get_metadata()
        assert meta.name != ""
        assert meta.update_frequency_seconds > 0

        # Mount
        await feed.mount()
        assert feed.is_mounted is True

        # Poll
        items = await feed.poll()
        assert len(items) > 0
        for it in items:
            assert it.feed_name == meta.name
            assert it.title != ""

        # Interpolate
        events = await feed.interpolate(items)
        assert len(events) == len(items)
        for ev in events:
            assert ev.source_feed == meta.name
            assert ev.event_type != ""

        # Unmount
        await feed.unmount()
        assert feed.is_mounted is False


def test_intelligence_graph_type_system():
    """Verify the 17 entity types and 13 relation types."""
    assert len(EntityType) == 17
    assert len(RelationType) == 13

    # Check categories
    assert EntityType.GOVERNMENT.category == EntityCategory.POWER
    assert EntityType.CORPORATION.category == EntityCategory.POWER
    assert EntityType.POLITICAL_LEADER.category == EntityCategory.AMPLIFIERS
    assert EntityType.DEMOGRAPHIC.category == EntityCategory.DEMOGRAPHICS
    assert EntityType.NARRATIVE.category == EntityCategory.NARRATIVE

    # Check relations
    assert RelationType.FUNDS.value == "funds"
    assert RelationType.PENETRATES.value == "penetrates"
    assert RelationType.TRICKLES_TO.value == "trickles_to"
    assert RelationType.INCENTIVE.value == "incentive"


@pytest.mark.asyncio
async def test_correlation_engine_organic_vs_astroturf_and_mesh_threat():
    """Verify organic confirmation vs astroturf detection and mesh threat check."""
    # 1. Setup mock hardware registry with an ARM64 OpenWrt router
    registry = HardwareRegistry()
    test_device = Device(
        device_id="dev_mesh_router_01",
        name="OpenWrt Gateway Router",
        device_type=DeviceType.IOT,
        role=DeviceRole.HOST,
        initial_trust_level=TrustLevel.TRUSTED,
        hardware=HardwareSpecs(cpu="arm64", has_camera=False, has_microphone=False),
        software=SoftwareSpecs(os="OpenWrt", os_version="23.05"),
        metadata={"vendor": "GL.iNet", "model": "AXT1800"},
    )
    await registry.register(test_device)

    engine = NarrativeCorrelationEngine(hardware_registry=registry)

    # 2. Case A: Organic Event (Confirmed by USGS earthquake telemetry)
    usgs = USGSFeed()
    await usgs.mount()
    raw_eq = await usgs.poll()
    eq_events = await usgs.interpolate(raw_eq)
    await usgs.unmount()

    corr_organic = engine.correlate(
        narrative_id="narrative_eq_california",
        narrative_title="Reports of strong shaking in Northern California",
        thematic_tags=["California", "Earthquake"],
        velocity_sigma=4.2,
        channel_burst_timestamps=[time.time(), time.time() + 30],
        physical_events=eq_events,
        spike_timestamp=time.time(),
        mesh_threat_check=False,
    )
    assert corr_organic.classification == NarrativeClassification.ORGANIC_EVENT
    assert corr_organic.matched_physical_event is not None
    assert corr_organic.confidence >= 0.90

    # 3. Case B: Manufactured Astroturf (3+ channels burst within 8 minutes without physical confirmation)
    now = time.time()
    burst_times = [now, now + 60, now + 180]  # Within 3 minutes
    corr_astroturf = engine.correlate(
        narrative_id="narrative_fake_wildfire",
        narrative_title="Massive explosions in remote forest",
        thematic_tags=["Forest", "Explosions"],
        velocity_sigma=3.8,
        channel_burst_timestamps=burst_times,
        physical_events=[],  # No physical confirmation
        spike_timestamp=now,
        mesh_threat_check=False,
    )
    assert corr_astroturf.classification == NarrativeClassification.MANUFACTURED_ASTROTURF
    assert corr_astroturf.astroturf_details is not None
    assert "ANOMALY ALERT" in corr_astroturf.alert_message

    # 4. Case C: Mesh Threat Check (CVE matches onboarded OpenWrt router)
    corr_cve = engine.correlate(
        narrative_id="narrative_cve_router",
        narrative_title="CVE-2026-9999 critical remote code execution on OpenWrt arm64 routers",
        thematic_tags=["CVE", "OpenWrt", "arm64", "router"],
        velocity_sigma=3.2,
        channel_burst_timestamps=[now],
        physical_events=[],
        spike_timestamp=now,
        mesh_threat_check=True,
    )
    assert corr_cve.mesh_threat is True
    assert "OpenWrt Gateway Router" in corr_cve.affected_mesh_devices
    assert "SECURITY ALERT: Affects mesh devices!" in corr_cve.alert_message


def test_chao1_demographic_virality_scorer():
    """Verify Chao1 nonparametric richness estimation and demographic penetration scoring."""
    scorer = DemographicViralityScorer()

    # Observed sample: 10 authors, some singletons (observed once) and doubletons (observed twice)
    observed = [
        "author_1", "author_1",  # doubleton
        "author_2", "author_2",  # doubleton
        "author_3",              # singleton
        "author_4",              # singleton
        "author_5",              # singleton
        "author_6",              # singleton
        "author_7",              # singleton
        "author_8",              # singleton
    ]
    # S = 8 unique authors
    # F1 = 6 singletons (author_3 to author_8)
    # F2 = 2 doubletons (author_1, author_2)
    # Chao1 richness S_est = 8 + (6^2 / (2 * 2)) = 8 + (36 / 4) = 8 + 9 = 17
    # Multiplier for "Scientific Researchers" = 3.0 -> N_est = 17 * 3.0 = 51

    n_est = scorer.estimate_community_size_chao1("Scientific Researchers", observed)
    assert n_est == 51

    # In a community of 51, a reach of 30 is 58.8% penetration!
    metric = scorer.compute_virality_score(
        demographic_name="Scientific Researchers",
        reach=30,
        engagement_rate=0.15,
        observed_authors=observed,
    )
    assert metric.penetration_ratio > 0.5
    # Score = (0.588 * 0.6 + 0.15 * 0.4) * 100 = (0.353 + 0.060) * 100 = 41.3 -> HIGH
    assert metric.score > 40.0
    assert metric.classification in ("HIGH", "CRITICAL")


@pytest.mark.asyncio
async def test_narrative_radar_full_cycle():
    """Verify NarrativeRadar full cycle execution and Daily Intelligence Brief."""
    radar = NarrativeRadar()
    await radar.mount_all_feeds()
    assert radar.is_running is True

    brief = await radar.execute_radar_cycle()
    assert brief is not None
    assert len(brief.active_branches) == 3
    assert len(brief.top_narratives) > 0
    assert radar.get_latest_brief() == brief

    await radar.unmount_all_feeds()
    assert radar.is_running is False
