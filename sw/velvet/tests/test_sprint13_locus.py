"""
Tests for Phase 3: Locus + Triangulation
"""

import pytest
import asyncio
from unittest.mock import MagicMock

from velvet.shen.locus import LocusEngine, LocationUpdate, haversine_distance
from velvet.shen.triangulation import TriangulationTask
from velvet.config import get_config


@pytest.fixture
def mock_locus():
    config = get_config()
    config.locus.enabled = True
    config.locus.seed_fences = [
        {"name": "home", "lat": 37.7749, "lon": -122.4194, "radius_meters": 100.0},
        {"name": "work", "lat": 37.3382, "lon": -121.8863, "radius_meters": 200.0}
    ]
    
    # Init locus without starting fabric subscriber
    locus = LocusEngine(start_subscriber=False)
    return locus


def test_haversine():
    # SF to SJ
    dist = haversine_distance(37.7749, -122.4194, 37.3382, -121.8863)
    # roughly 68 km
    assert 60000 < dist < 80000


@pytest.mark.asyncio
async def test_locus_location_tracking(mock_locus):
    # Simulate SF update
    payload_sf = {
        "device_id": "phone-1",
        "lat": 37.7750, 
        "lon": -122.4195,
        "timestamp": "2023-01-01T12:00:00Z"
    }
    
    await mock_locus._handle_location(payload_sf)
    
    loc = mock_locus.get_device_location("phone-1")
    assert loc is not None
    assert loc.lat == 37.7750
    
    # Check geofences
    fences = mock_locus.get_current_fences(loc.lat, loc.lon)
    assert "home" in fences
    assert "work" not in fences
    
    assert mock_locus.is_device_in_fence("phone-1", "home") is True


@pytest.mark.asyncio
async def test_triangulation_task(mock_locus):
    task = TriangulationTask(locus=mock_locus)
    assert task.name() == "triangulation"
    
    # Run mock task
    await task.run([MagicMock()])
