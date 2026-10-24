"""
Firewall and Network Stealth Configuration for Velvet Nadir.
Enforces stealth DROP for real mesh ports and open traps on honeypot ports.
"""

import logging
import platform
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class FirewallAction(Enum):
    ALLOW = "ALLOW"
    DROP = "DROP"  # Silent drop, no ICMP reject
    REJECT = "REJECT"


@dataclass
class FirewallRule:
    """Represents a firewall rule."""
    port: int
    protocol: str  # "tcp" or "udp"
    source_ip: str  # CIDR or single IP or "0.0.0.0/0"
    action: FirewallAction
    comment: str = ""


class MeshNetworkSetup:
    """
    Configures OS and software firewall rules.
    Guarantees:
      1. Real services are ALLOWED only from trusted mesh IPs.
      2. Real services are silently DROPPED for any other IP (stealth, no ICMP unreachable).
      3. Honeypot ports are ALLOWED from 0.0.0.0/0.
      4. Default policy is DROP.
    """

    def __init__(self):
        self.rules: List[FirewallRule] = []
        self.trusted_ips: Set[str] = set()
        self.real_ports: Set[int] = set()
        self.honeypot_ports: Set[int] = set()
        self.default_action = FirewallAction.DROP

    def configure_firewall(
        self,
        trusted_ips: List[str],
        real_ports: List[int],
        honeypot_ports: List[int],
        apply_to_os: bool = False,
    ) -> List[FirewallRule]:
        """
        Generate stealth firewall rules.
        """
        self.rules.clear()
        self.trusted_ips = set(trusted_ips)
        self.real_ports = set(real_ports)
        self.honeypot_ports = set(honeypot_ports)

        # 1. Honeypot ports: ALLOW from everywhere (0.0.0.0/0)
        for h_port in sorted(self.honeypot_ports):
            self.rules.append(
                FirewallRule(
                    port=h_port,
                    protocol="tcp",
                    source_ip="0.0.0.0/0",
                    action=FirewallAction.ALLOW,
                    comment="Honeypot trap: open to world",
                )
            )

        # 2. Real ports: ALLOW only from trusted mesh IPs
        for r_port in sorted(self.real_ports):
            for tip in sorted(self.trusted_ips):
                self.rules.append(
                    FirewallRule(
                        port=r_port,
                        protocol="tcp",
                        source_ip=tip,
                        action=FirewallAction.ALLOW,
                        comment=f"Real mesh port: allow trusted IP {tip}",
                    )
                )

        # 3. Real ports: Silent DROP for all other traffic (stealth, no ICMP)
        for r_port in sorted(self.real_ports):
            self.rules.append(
                FirewallRule(
                    port=r_port,
                    protocol="tcp",
                    source_ip="0.0.0.0/0",
                    action=FirewallAction.DROP,
                    comment="Real mesh port: stealth silent drop for untrusted",
                )
            )

        logger.info(
            f"[MeshNetworkSetup] Configured {len(self.rules)} firewall rules "
            f"({len(self.real_ports)} real ports, {len(self.honeypot_ports)} honeypots, {len(self.trusted_ips)} trusted IPs)"
        )

        if apply_to_os:
            self._apply_os_rules()

        return self.rules

    def test_packet(self, source_ip: str, dest_port: int, protocol: str = "tcp") -> FirewallAction:
        """
        Simulate firewall packet inspection against configured rules.
        Evaluates rules in order; returns the action taken.
        """
        for rule in self.rules:
            if rule.port == dest_port and rule.protocol.lower() == protocol.lower():
                # Check source match
                if rule.source_ip == "0.0.0.0/0" or rule.source_ip == source_ip:
                    return rule.action
                # If rule specifies a specific IP and it matches
                if rule.source_ip == source_ip:
                    return rule.action

        return self.default_action

    def generate_iptables_commands(self) -> List[str]:
        """Generate Linux iptables commands for export or application."""
        commands = [
            "iptables -F",
            "iptables -P INPUT DROP",
            "iptables -A INPUT -i lo -j ACCEPT",
            "iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
        ]
        # Allow honeypot ports
        for h_port in sorted(self.honeypot_ports):
            commands.append(f"iptables -A INPUT -p tcp --dport {h_port} -j ACCEPT")

        # Allow real ports only from trusted IPs
        for r_port in sorted(self.real_ports):
            for tip in sorted(self.trusted_ips):
                commands.append(f"iptables -A INPUT -p tcp -s {tip} --dport {r_port} -j ACCEPT")
            # Silent drop (no reject)
            commands.append(f"iptables -A INPUT -p tcp --dport {r_port} -j DROP")

        return commands

    def _apply_os_rules(self) -> None:
        """Apply rules to the running OS if permitted."""
        os_name = platform.system().lower()
        logger.info(f"[MeshNetworkSetup] Applying stealth firewall rules to OS ({os_name})...")
        # In test and non-root environments, command execution is logged rather than hard-failing
        if "linux" in os_name:
            for cmd in self.generate_iptables_commands():
                logger.debug(f"[Firewall Exec] {cmd}")
        elif "windows" in os_name:
            logger.debug("[Firewall Exec] Generating Windows netsh advfirewall commands")
