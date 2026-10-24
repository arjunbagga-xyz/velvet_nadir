"""
Privacy BreathTasks for Velvet Nadir background execution.
"""

from .metadata_stripper import MetadataStripperTask
from .honeypot_monitor import HoneypotMonitor
from .narrative_radar_task import NarrativeRadarTask
from .canary_monitor import CanaryMonitor
from .phantom_manager import PhantomPersonaManager
from .tracker_polluter import TrackerPolluter
from .ai_tool_noise import AIToolNoise

__all__ = [
    "MetadataStripperTask",
    "HoneypotMonitor",
    "NarrativeRadarTask",
    "CanaryMonitor",
    "PhantomPersonaManager",
    "TrackerPolluter",
    "AIToolNoise",
]
