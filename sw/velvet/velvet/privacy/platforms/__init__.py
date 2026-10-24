"""
Platform-specific privacy and defense poison modules.
Provides the PlatformPoisonModule base class and auto-activation registry.
"""

from abc import ABC, abstractmethod
import logging
from typing import Dict, List, Optional, Any, Union

from ..egress_guard import ContentType, PrivacyStrength
from ..identity_registry import Account, identity_registry
from ..perturbation import PerturbationEngine
from ..metadata_strip import MetadataStripper
from ..style_guard import StyleGuard

logger = logging.getLogger(__name__)


class PlatformPoisonModule(ABC):
    """
    Abstract Base Class for platform defense modules.
    Adheres strictly to the rule:
    Real accounts are never poisoned; only phantom traffic is modified or simulated.
    """
    platform_name: str
    
    def __init__(self, platform_name: str):
        self.platform_name = platform_name.lower()
        self.real_account: Optional[Account] = None
        self.phantom_accounts: List[Account] = []
        self.metadata_stripper = MetadataStripper()
        self.perturbation_engine = PerturbationEngine(PrivacyStrength.BALANCED)
        self.style_guard = StyleGuard(PrivacyStrength.BALANCED)
        self.is_active: bool = False

    def activate(self, real_account: Optional[Account] = None) -> None:
        """Activate the poison module for this platform."""
        self.real_account = real_account or identity_registry.get_real_account(self.platform_name)
        self.phantom_accounts = identity_registry.get_phantom_accounts(self.platform_name)
        self.is_active = True
        logger.info(f"[PlatformModule] Activated {self.platform_name} module (Phantoms: {len(self.phantom_accounts)})")

    @abstractmethod
    def supported_features(self) -> Dict[str, Any]:
        """Return dict of supported privacy and defense features for this platform."""
        ...

    @abstractmethod
    async def apply_egress_filter(
        self,
        content: Union[str, bytes],
        content_type: ContentType,
        is_phantom: bool = False,
        **kwargs
    ) -> Union[str, bytes]:
        """
        Filter and perturb outgoing content for this platform.
        User/real account words are never modified for style.
        """
        ...

    def get_phantom_actions(self) -> List[Dict[str, Any]]:
        """Return scheduled decoy actions for phantom personas (follows, browsing, etc.)."""
        return []


_MODULE_REGISTRY: Dict[str, PlatformPoisonModule] = {}


def register_platform_module(module: PlatformPoisonModule) -> None:
    """Register a platform poison module."""
    _MODULE_REGISTRY[module.platform_name] = module


def get_platform_module(platform: str) -> Optional[PlatformPoisonModule]:
    """Retrieve platform module by name, initializing if needed."""
    plat = platform.lower()
    if plat not in _MODULE_REGISTRY:
        if "instagram" in plat:
            from .instagram import InstagramPoisonModule
            _MODULE_REGISTRY[plat] = InstagramPoisonModule()
        elif "twitter" in plat or plat == "x":
            from .twitter import TwitterPoisonModule
            _MODULE_REGISTRY[plat] = TwitterPoisonModule()
        else:
            from .generic_web import GenericWebPoisonModule
            _MODULE_REGISTRY[plat] = GenericWebPoisonModule(plat)
    return _MODULE_REGISTRY.get(plat)


def activate_platform_for_account(account: Account) -> None:
    """Auto-activates the module when a real account is registered in identity_registry."""
    module = get_platform_module(account.platform)
    if module:
        module.activate(account)
