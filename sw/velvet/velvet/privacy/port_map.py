"""
Port map management for Velvet Nadir Honeypot System.
Manages randomization of ports and integration with BasiliskEnclave.
"""

import random
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List
from loguru import logger
from velvet.basilisk import BasiliskEnclave

DEFAULT_HONEYPOT_SERVICES: List[str] = [
    "ssh",
    "mysql",
    "rest_debug",
    "https_admin",
    "s3_minio",
    "postgres",
    "openwrt",
    "redis",
    "mongodb",
    "vnc",
    "docker_socket",
    "k8s_api",
]

@dataclass
class PortMap:
    """Maps logical services to randomized non-standard ports."""
    services: Dict[str, int] = field(default_factory=dict)
    grace_period_services: Dict[str, int] = field(default_factory=dict)
    
    @classmethod
    def generate(cls, services_list: List[str] | None = None) -> "PortMap":
        """Create fresh randomized port assignments, verify no collisions."""
        pm = cls()
        assigned = set()
        svcs = services_list or DEFAULT_HONEYPOT_SERVICES
        for svc in svcs:
            while True:
                port = random.randint(30000, 65000)
                if port not in assigned:
                    assigned.add(port)
                    pm.services[svc] = port
                    break
        return pm

    def rotate(self, services_list: List[str] | None = None) -> None:
        """Rotates ports, moving current ports to grace period."""
        self.grace_period_services = self.services.copy()
        svcs = services_list or list(self.grace_period_services.keys()) or DEFAULT_HONEYPOT_SERVICES
        self.services.clear()
        
        assigned = set(self.grace_period_services.values())
        for svc in svcs:
            while True:
                port = random.randint(30000, 65000)
                if port not in assigned:
                    assigned.add(port)
                    self.services[svc] = port
                    break
                    
    def store_in_enclave(self, enclave: BasiliskEnclave) -> None:
        """Store the port map securely in a BasiliskEnclave."""
        enclave.put("honeypot_port_map", self.to_dict())
        
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transmission."""
        return asdict(self)
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortMap":
        """Deserialize."""
        return cls(**data)
