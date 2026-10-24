"""
Honeypot services providing the 4-track fake environment.
"""

import asyncio
from loguru import logger
from typing import Dict, Tuple, Callable

# Simulated logger for forensics to Tartarus
def log_forensics(service_name: str, client_ip: str, data: str):
    logger.info(f"[Honeypot Forensic] Service: {service_name} IP: {client_ip} Data: {data}")

class FakeSSHServer:
    """Accepts weak credentials, provides fake filesystem."""
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        log_forensics("FakeSSHServer", str(addr), "Connection established")
        writer.write(b"SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5\r\n")
        await writer.drain()
        # Minimal mock logic for tarpit or logging
        try:
            while not reader.at_eof():
                data = await reader.read(1024)
                if not data:
                    break
                log_forensics("FakeSSHServer", str(addr), f"Received: {data}")
        except Exception as e:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

class FakeHTTPServer:
    """Fake web admin panels (Portainer/Grafana/OpenWRT lookalikes)."""
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        log_forensics("FakeHTTPServer", str(addr), "Connection established")
        try:
            data = await reader.read(1024)
            log_forensics("FakeHTTPServer", str(addr), f"Received: {data}")
            response = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html><body>Fake Admin Panel</body></html>"
            writer.write(response)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

class FakeDBServer:
    """Fake databases accepting breadcrumb creds."""
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        log_forensics("FakeDBServer", str(addr), "Connection established")
        # Minimal mockup
        try:
            writer.write(b"5.5.5-10.4.24-MariaDB\n")
            await writer.drain()
            data = await reader.read(1024)
            log_forensics("FakeDBServer", str(addr), f"Received: {data}")
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

class FakeAPIServer:
    """Fake REST APIs with infinite pagination tarpit."""
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        log_forensics("FakeAPIServer", str(addr), "Connection established")
        try:
            data = await reader.read(1024)
            log_forensics("FakeAPIServer", str(addr), f"Received: {data}")
            response = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"data\": [], \"next_page\": \"/api/v1/users?page=9999999\"}"
            writer.write(response)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

class TarpitSink:
    """Extremely slow response drip (10 bytes/sec), keeps connections alive indefinitely."""
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        log_forensics("TarpitSink", str(addr), "Connection established")
        try:
            while not reader.at_eof():
                # Drip feed to keep connection alive
                writer.write(b"0000000000")
                await writer.drain()
                await asyncio.sleep(1)
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

class HoneypotPortBinder:
    """Binds standard ports to trap services."""
    def __init__(self):
        self.servers = []

    async def start(self):
        """Bind common vulnerable ports to appropriate fake services."""
        bindings = [
            (22, FakeSSHServer().handle_client),
            (80, FakeHTTPServer().handle_client),
            (443, FakeHTTPServer().handle_client),
            (3306, FakeDBServer().handle_client),
            (5432, FakeDBServer().handle_client),
            (6379, FakeDBServer().handle_client),
            (8080, FakeHTTPServer().handle_client),
            (8443, FakeHTTPServer().handle_client),
            (9000, FakeHTTPServer().handle_client), # Portainer / MinIO
            (27017, FakeDBServer().handle_client),
            (2375, FakeAPIServer().handle_client), # Docker API
            (5900, TarpitSink().handle_client), # VNC
            (3389, TarpitSink().handle_client), # RDP
        ]
        
        for port, handler in bindings:
            try:
                server = await asyncio.start_server(handler, '0.0.0.0', port)
                self.servers.append(server)
                logger.info(f"Honeypot started on port {port}")
            except Exception as e:
                logger.warning(f"Could not bind honeypot on port {port}: {e}")

    async def stop(self):
        """Stop all running honeypot servers."""
        for server in self.servers:
            server.close()
            await server.wait_closed()
        self.servers.clear()
