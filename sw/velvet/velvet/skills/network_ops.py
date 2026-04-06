"""
Network Operations Skills.

Capabilities:
- Network Scanning (ARP + Port Scan)
- Remote Command Execution (SSH)
- Agentic Deployment (SSH + ADB)
"""

import asyncio
import socket
import logging
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from . import skill, SkillCategory, SkillParameter, AutonomyLevel, SkillResult
from ..scan import NetworkScanner, ScannedDevice

# ============================================================================
# Scanning Skills
# ============================================================================

@skill(
    name="scan_local_network",
    description="Scan the local network for devices and open ports (SSH, ADB, Web).",
    category=SkillCategory.PERCEPTION,
    parameters=[
        SkillParameter("deep_scan", "bool", "If True, checks for open ports on found devices", required=False, default=False)
    ],
    tags=["network", "discovery", "security"]
)
async def scan_local_network(deep_scan: bool = False) -> SkillResult:
    """Scan the network using ARP and optional port checks."""
    logger.info(f"Starting network scan (deep={deep_scan})...")
    
    # Base ARP scan
    devices = await NetworkScanner.scan_arp()
    
    if not devices:
        return SkillResult.ok(data=[], speak="I didn't find any devices on the local network.")
        
    results = []
    
    for device in devices:
        dev_info = {
            "ip": device.ip_address,
            "mac": device.mac_address,
            "name": device.name,
            "open_ports": []
        }
        
        if deep_scan:
            scan_result = await NetworkScanner.scan_nmap(device.ip_address, ports=[22, 5555, 80, 7447])
            open_ports = scan_result.get("open_ports", [])
            dev_info["open_ports"] = open_ports
            
            # Identify potential roles
            roles = []
            if 22 in open_ports: roles.append("SSH Node")
            if 5555 in open_ports: roles.append("Android Device")
            if 7447 in open_ports: roles.append("Velvet Mesh Node")
            
            dev_info["potential_roles"] = roles
            
        results.append(dev_info)
        
    count = len(results)
    summary = f"Found {count} devices."
    if deep_scan:
        ssh_nodes = sum(1 for d in results if 22 in d["open_ports"])
        adb_nodes = sum(1 for d in results if 5555 in d["open_ports"])
        if ssh_nodes: summary += f" {ssh_nodes} have SSH open."
        if adb_nodes: summary += f" {adb_nodes} look like Android devices."
        
    return SkillResult.ok(data=results, speak=summary)


# ============================================================================
# Deployment Skills
# ============================================================================

# NOTE: No default SSH credentials. Always require explicit credentials.\n

@skill(
    name="deploy_velvet_node",
    description="Deploy Velvet Client to a remote device via SSH or ADB.",
    category=SkillCategory.ROBOTICS, # Or SPECIALIST? ROBOTICS fits "Agentic Actuation"
    parameters=[
        SkillParameter("target_ip", "string", "IP address of the target device"),
        SkillParameter("method", "string", "Deployment method: 'ssh', 'adb', or 'auto'", required=False, default="auto"),
        SkillParameter("user", "string", "SSH Username (if method is ssh)", required=False, default=None),
        SkillParameter("password", "string", "SSH Password (if method is ssh)", required=False, default=None),
    ],
    autonomy=AutonomyLevel.LEVEL_2, # Requires confirmation
    tags=["deployment", "setup", "hacking"]
)
async def deploy_velvet_node(
    target_ip: str, 
    method: str = "auto", 
    user: str | None = None, 
    password: str | None = None
) -> SkillResult:
    """Deploy the Velvet Client to a target device."""
    
    # 1. Strategy Selection
    if method == "auto":
        # probe ports to decide
        method = "manual" # Default fallback
        try:
            # Check ADB
            fut = asyncio.open_connection(target_ip, 5555)
            r, w = await asyncio.wait_for(fut, timeout=1.0)
            w.close()
            method = "adb"
        except:
            try:
                # Check SSH
                fut = asyncio.open_connection(target_ip, 22)
                r, w = await asyncio.wait_for(fut, timeout=1.0)
                w.close()
                method = "ssh"
            except:
                pass
    
    logger.info(f"Deploying to {target_ip} using method: {method}")
    
    if method == "adb":
        return await _deploy_via_adb(target_ip)
    elif method == "ssh":
        # Credentials handling
        # In a real app, we'd look up a Vault or ask the user.
        # For MVP, we fail if not provided, or use defaults for Pi.
        u = user
        p = password
        if not u or not p:
            return SkillResult.fail("SSH Username and Password are required for deployment.")
            
        return await _deploy_via_ssh(target_ip, u, p)
    else:
        # Manual fallback
        cmd = f"curl -sL https://velvet-nadir.s3.amazonaws.com/install.sh | bash -s -- --connect {target_ip}" # hypothetical URL
        return SkillResult.ok(
            speak=f"I can't connect automatically. Please run this command on the device: {cmd}",
            display={"command": cmd}
        )


async def _deploy_via_adb(ip: str) -> SkillResult:
    """Deploy using Android Debug Bridge."""
    try:
        # 1. Connect
        logger.info(f"ADB: Connecting to {ip}...")
        proc = await asyncio.create_subprocess_exec(
            "adb", "connect", ip,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if b"connected to" not in stdout:
            return SkillResult.fail(f"ADB Connection failed: {stdout.decode()} {stderr.decode()}")
            
        # 2. Push Payload (Using a tiny bootstrap script for now)
        # Real implementation would push a .whl or a zip of the source
        bootstrap_code = "import urllib.request; exe = urllib.request.urlopen('http://YOUR_HOST_IP/bootstrap.py').read(); exec(exe)"
        # For MVP, let's just push a "Hello World" probe to prove control
        
        cmd = f"print('Velvet Injection Successful on Android')"
        
        # 3. Execute
        proc_exec = await asyncio.create_subprocess_exec(
            "adb", "-s", f"{ip}:5555", "shell", "python", "-c", f"\"{cmd}\"",
             stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, err = await proc_exec.communicate()
        
        if proc_exec.returncode == 0:
            return SkillResult.ok(
                speak="Successfully connected to Android device via ADB and executed payload.",
                data={"output": out.decode().strip()}
            )
        else:
            return SkillResult.fail(f"ADB Execution failed: {err.decode()}")

    except FileNotFoundError:
        return SkillResult.fail("ADB tool not found on Host. Please install android-tools.")
    except Exception as e:
        return SkillResult.fail(f"ADB Error: {e}")


async def _deploy_via_ssh(ip: str, user: str, password: str) -> SkillResult:
    """Deploy using SSH (asyncssh via NativeDriver)."""
    try:
        from ..drivers import NativeDriver, ConnectionInfo, ConnectionMethod
        
        driver = NativeDriver()
        conn_info = ConnectionInfo(
            method=ConnectionMethod.SSH,
            address=ip,
            username=user,
            password=password,
        )
        
        if not await driver.connect(conn_info):
            return SkillResult.fail("SSH connection failed.")
        
        # Check Python
        version = await driver.run_command("python3 --version")
        if "Python 3" not in version:
            await driver.disconnect()
            return SkillResult.fail(f"Target does not have Python 3 (found: {version})")
        
        # Deploy (inject_velvet handles certs + install + config)
        device_id = ip.replace(".", "_")
        await driver.inject_velvet(device_id)
        await driver.disconnect()
        
        return SkillResult.ok(
            speak=f"Deployed to {ip}. Found {version.strip()}. Velvet installed with mTLS certs.",
            data={"version": version.strip()}
        )
        
    except Exception as e:
        return SkillResult.fail(f"SSH Error: {e}")
