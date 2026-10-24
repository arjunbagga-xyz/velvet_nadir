"""
TrustProvisioner (Sprint 24)

Securely pushes the Basilisk Enclave ca.key to biometrically verified devices
over SFTP. Used when a device is promoted from UNTRUSTED to fully trusted.
"""
import asyncio
import os
from pathlib import Path
from loguru import logger

class TrustProvisioner:
    def __init__(self, key_path: str = None):
        from velvet.config import get_config
        self.config = get_config()
        self.key_path = key_path or getattr(self.config.security, "ca_key_path", "ca.key")
        
    async def provision_device(self, host: str, username: str, password: str = None, key_filename: str = None, target_path: str = "/opt/velvet/certs/ca.key") -> bool:
        """
        Securely copy the CA key to the remote device using asyncssh.
        """
        if not os.path.exists(self.key_path):
            logger.error(f"[TrustProvisioner] CA key not found at {self.key_path}")
            return False
            
        logger.info(f"[TrustProvisioner] Provisioning CA key to {host}:{target_path}")
        try:
            import asyncssh
            
            connect_kwargs = {}
            if password:
                connect_kwargs["password"] = password
            if key_filename:
                connect_kwargs["client_keys"] = [key_filename]
                
            async with asyncssh.connect(host, username=username, known_hosts=None, **connect_kwargs) as conn:
                async with conn.start_sftp_client() as sftp:
                    await sftp.put(self.key_path, target_path)
                    await sftp.chmod(target_path, 0o600)  # Secure permissions
                    
            logger.info(f"[TrustProvisioner] Successfully provisioned {host}")
            return True
        except ImportError:
            logger.error("[TrustProvisioner] asyncssh not installed. Cannot provision device via SFTP.")
            return False
        except Exception as e:
            logger.error(f"[TrustProvisioner] Provisioning failed for {host}: {e}")
            return False
