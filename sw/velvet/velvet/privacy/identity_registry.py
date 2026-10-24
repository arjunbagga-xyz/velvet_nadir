"""
Identity Registry: Strict separation of Real vs. Phantom accounts.
Guarantees that real accounts are never poisoned and only phantom/decoy traffic
is perturbed, polluted, or used for honeypot operations.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class Account:
    """Represents an online persona/account."""
    id: str
    platform: str
    username: str
    is_real: bool
    display_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    credentials: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class IdentityRegistry:
    """
    Manages accounts across all platforms.
    Hard Rule: Real accounts are never poisoned. Internal mesh Zenoh communications are untouched.
    Only public internet egress passes through EgressGuard.
    """

    def __init__(self):
        self._real_accounts: Dict[str, Dict[str, Account]] = {}  # platform -> {username: Account}
        self._phantom_accounts: Dict[str, Dict[str, Account]] = {}  # platform -> {username: Account}
        self._on_real_registered_callbacks: List[Callable[[Account], Any]] = []

    def register_listener(self, callback: Callable[[Account], Any]) -> None:
        """Register a callback for when a real account is registered (for auto-activation)."""
        self._on_real_registered_callbacks.append(callback)

    def register_real_account(
        self,
        platform: str,
        username: str,
        display_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Account:
        """
        Register a real user account.
        Hard Rule: Real accounts are NEVER poisoned or stylometrically shifted.
        Automatically triggers:
          1. Platform poison module activation.
          2. Auto-provisioning of 2-3 phantom accounts for decoy shielding.
          3. Platform tracker pollution registration.
        """
        plat = platform.lower()
        if plat not in self._real_accounts:
            self._real_accounts[plat] = {}

        account_id = f"real_{plat}_{username}"
        account = Account(
            id=account_id,
            platform=plat,
            username=username,
            is_real=True,
            display_name=display_name or username,
            metadata=metadata or {},
            credentials=credentials or {},
        )
        self._real_accounts[plat][username] = account
        logger.info(f"[IdentityRegistry] Registered REAL account: {account_id} (PROTECTED: Never poisoned)")

        # Auto-provision 2-3 phantom accounts to shield the real account
        for i in range(1, 4):
            phantom_user = f"decoy_{username}_{i}"
            self.register_phantom_account(
                platform=plat,
                username=phantom_user,
                display_name=f"User {i}",
                metadata={"purpose": "shielding", "target_real_user": username},
            )

        # Notify callbacks for platform module activation
        for cb in self._on_real_registered_callbacks:
            try:
                cb(account)
            except Exception as e:
                logger.error(f"[IdentityRegistry] Callback failed during real account registration: {e}")

        # Auto-activate platform module if available
        try:
            from .platforms import activate_platform_for_account
            activate_platform_for_account(account)
        except ImportError:
            pass

        return account

    def register_phantom_account(
        self,
        platform: str,
        username: str,
        display_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Account:
        """Register a synthetic/decoy phantom account."""
        plat = platform.lower()
        if plat not in self._phantom_accounts:
            self._phantom_accounts[plat] = {}

        account_id = f"phantom_{plat}_{username}"
        account = Account(
            id=account_id,
            platform=plat,
            username=username,
            is_real=False,
            display_name=display_name or username,
            metadata=metadata or {},
            credentials=credentials or {},
        )
        self._phantom_accounts[plat][username] = account
        logger.debug(f"[IdentityRegistry] Registered PHANTOM account: {account_id}")
        return account

    def get_real_account(self, platform: str) -> Optional[Account]:
        """Get the primary real account for a platform."""
        accounts = self._real_accounts.get(platform.lower(), {})
        if accounts:
            return next(iter(accounts.values()))
        return None

    def get_phantom_accounts(self, platform: str) -> List[Account]:
        """Get all phantom accounts for a platform."""
        return list(self._phantom_accounts.get(platform.lower(), {}).values())

    def is_real_account(self, platform: str, username: str) -> bool:
        """Check if an account is a registered real account."""
        plat = platform.lower()
        return username in self._real_accounts.get(plat, {})

    def is_phantom_account(self, platform: str, username: str) -> bool:
        """Check if an account is a synthetic phantom account."""
        plat = platform.lower()
        return username in self._phantom_accounts.get(plat, {})

    def get_all_real_accounts(self) -> List[Account]:
        """Get all real accounts across all platforms."""
        result = []
        for plat_accounts in self._real_accounts.values():
            result.extend(plat_accounts.values())
        return result

    def get_all_phantom_accounts(self) -> List[Account]:
        """Get all phantom accounts across all platforms."""
        result = []
        for plat_accounts in self._phantom_accounts.values():
            result.extend(plat_accounts.values())
        return result


# Global singleton
identity_registry = IdentityRegistry()
