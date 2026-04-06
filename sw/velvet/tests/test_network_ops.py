import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Mock paramiko BEFORE import
sys.modules["paramiko"] = MagicMock()

import asyncio
from velvet.skills.network_ops import deploy_velvet_node, scan_local_network
from velvet.scan import ScannedDevice

class TestNetworkOps(unittest.IsolatedAsyncioTestCase):
    
    @patch("velvet.skills.network_ops.NetworkScanner.scan_arp")
    @patch("velvet.skills.network_ops.NetworkScanner.scan_nmap")
    async def test_scan_local_network_deep(self, mock_scan_nmap, mock_scan_arp):
        # Mock ARP results
        mock_scan_arp.return_value = [
            ScannedDevice(id="192.168.1.50", name="TestPi", scan_type="arp", ip_address="192.168.1.50")
        ]
        
        # Mock port scan: 22 open
        mock_scan_nmap.return_value = {"open_ports": [22]}
        
        result = await scan_local_network(deep_scan=True)
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.data), 1)
        self.assertIn(22, result.data[0]["open_ports"])
        self.assertIn("SSH Node", result.data[0]["potential_roles"])

    @patch("velvet.drivers.NativeDriver")
    async def test_deploy_ssh_success(self, mock_driver_cls):
        mock_driver = MagicMock()
        # Ensure connect() and others return Futures/coroutines
        mock_driver.connect = AsyncMock(return_value=True)
        mock_driver.run_command = AsyncMock(return_value="Python 3.11.2")
        mock_driver.inject_velvet = AsyncMock(return_value=True)
        mock_driver.disconnect = AsyncMock()
        
        mock_driver_cls.return_value = mock_driver
        
        result = await deploy_velvet_node(target_ip="192.168.1.10", method="ssh", user="pi", password="raspberry")
        
        self.assertTrue(result.success)
        mock_driver.connect.assert_called_once()
        mock_driver.run_command.assert_called_with("python3 --version")
        mock_driver.inject_velvet.assert_called_with("192_168_1_10")
        mock_driver.disconnect.assert_called_once()

    @patch("asyncio.create_subprocess_exec")
    async def test_deploy_adb_success(self, mock_subprocess):
        # Mock ADB Connect success
        proc_connect = AsyncMock()
        proc_connect.communicate.return_value = (b"connected to 192.168.1.10:5555", b"")
        proc_connect.returncode = 0
        
        # Mock ADB Exec success
        proc_exec = AsyncMock()
        proc_exec.communicate.return_value = (b"Velvet Injection Successful", b"")
        proc_exec.returncode = 0
        
        mock_subprocess.side_effect = [proc_connect, proc_exec]
        
        result = await deploy_velvet_node(target_ip="192.168.1.10", method="adb")
        
        self.assertTrue(result.success)
        self.assertIn("Successfully connected", result.speak)

if __name__ == "__main__":
    unittest.main()
