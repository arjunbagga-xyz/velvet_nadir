"""
Project Shen: The Cognitive Mesh for Velvet.

Implements the Yi/Po/Hun/Jing taxonomy with Sprint 10 additions:
  - Tartarus: Cold memory archive
  - MeshMemorySync: Hive mind replication
  - Xi: Background task manager + BreathTasks
  - Trust, Affinity, Saraswati: User trust, model learning, skill learning
"""

from .yi import Yi
from .po import Po
from .hun import Hun
from .jing import Jing
from .polymath import Polymath
from .tartarus import ColdStore
from .mesh_memory import MeshMemorySync
from .xi import Xi, BreathTask, ComputeBudget, ConversationTurn, XiJournal
from .fuxi import Fuxi
from .agni import Agni
from .trust import TrustEngine, TrustDecision
from .affinity import ModelAffinityTracker
from .inari import Inari
from .device_watchdog import DeviceWatchdog
from .saraswati import Saraswati, Shruti, Smriti, Vidya

__all__ = [
    "Yi", "Po", "Hun", "Jing", "Polymath",
    "ColdStore", "MeshMemorySync",
    "Xi", "BreathTask", "ComputeBudget", "ConversationTurn", "XiJournal",
    "Fuxi", "Agni", "Inari", "DeviceWatchdog",
    "TrustEngine", "TrustDecision", "ModelAffinityTracker",
    "Saraswati", "Shruti", "Smriti", "Vidya",
]

