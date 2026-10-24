"""
Honeypot Vulnerability Tracks, Credential Chaining Web & Tarpits.
Implements the 4-track deception architecture with interconnected honeypot traps.
"""

import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def log_honeypot_forensic(
    trap: str,
    attacker_ip: str,
    method: str,
    payload: Any,
    db_path: Optional[Path] = None,
    geoip: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Log honeypot interaction to Tartarus SQLite cold storage.
    category: honeypot_forensics
    """
    if db_path is None:
        db_path = Path.home() / ".velvet" / "tartarus.db"
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    record = {
        "trap": trap,
        "attacker_ip": attacker_ip,
        "method": method,
        "payload": payload if isinstance(payload, dict) else {"raw": str(payload)},
        "timestamp": ts,
        "geoip": geoip or {"country": "LOCAL", "asn": "LOCAL"},
    }

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS honeypot_forensics (
                    id TEXT PRIMARY KEY,
                    trap TEXT NOT NULL,
                    attacker_ip TEXT NOT NULL,
                    method TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    geoip TEXT NOT NULL
                )
            """)
            record_id = f"forensic_{int(time.time() * 1000)}_{trap}"
            conn.execute("""
                INSERT INTO honeypot_forensics (id, trap, attacker_ip, method, payload, timestamp, geoip)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                trap,
                attacker_ip,
                method,
                json.dumps(record["payload"]),
                record["timestamp"],
                json.dumps(record["geoip"]),
            ))
            conn.commit()
    except Exception as e:
        logger.error(f"[HoneypotForensics] Failed to write forensic log to Tartarus: {e}")

    logger.warning(f"🚨 [Honeypot Forensic] {trap} hit by {attacker_ip} via {method}: {payload}")
    return record


# =====================================================================
# Tarpits
# =====================================================================

class Tarpit1InfinitePagination:
    """Tarpit 1: Infinite pagination slow drip (0.5s/chunk), keeping attacker blocked."""
    def __init__(self, infinite: bool = False):
        self.infinite = infinite

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("tarpit_infinite_pagination", client_ip, "HTTP_GET", "/api/v1/users")
        try:
            page = 1
            writer.write(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Type: application/json\r\n\r\n")
            await writer.drain()

            while self.infinite or page < 50:  # Bound iteration in test, infinite in production
                chunk_data = json.dumps({
                    "page": page,
                    "results": [{"user_id": page * 100 + i, "token": f"fake_tok_{page}_{i}"} for i in range(5)],
                    "next_page": f"/api/v1/users?page={page + 1}",
                }).encode("utf-8")
                
                chunk_hdr = f"{len(chunk_data):X}\r\n".encode("ascii")
                writer.write(chunk_hdr + chunk_data + b"\r\n")
                await writer.drain()
                page += 1
                await asyncio.sleep(0.1 if not self.infinite else 0.5)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class Tarpit2DelayedSyntheticDump:
    """Tarpit 2: Delayed synthetic JSON dump for database callers."""
    def __init__(self, infinite: bool = False):
        self.infinite = infinite

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("tarpit_synthetic_dump", client_ip, "DB_STREAM", "postgres_canary_dump")
        try:
            writer.write(b"POSTGRES_DUMP_START\n")
            await writer.drain()
            i = 0
            while self.infinite or i < 10:
                await asyncio.sleep(0.1 if not self.infinite else 0.5)
                writer.write(f"RECORD_{i}: DUMPING TABLE PARTITION_{i}...\n".encode("utf-8"))
                await writer.drain()
                i += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class Tarpit3EverGrowingStream:
    """Tarpit 3: Ever-growing query result stream for NoSQL callers."""
    def __init__(self, infinite: bool = False):
        self.infinite = infinite

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("tarpit_ever_growing_stream", client_ip, "MONGO_CURSOR", "users_pii")
        try:
            idx = 0
            while self.infinite or idx < 20:
                await asyncio.sleep(0.05 if not self.infinite else 0.5)
                writer.write(f'{{"_id": "{idx}", "data": "pii_record_stream_{idx}"}}\n'.encode("utf-8"))
                await writer.drain()
                idx += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class Tarpit4ExponentialDelay:
    """Tarpit 4: Exponential delay generator for management API callers."""
    def __init__(self, infinite: bool = False):
        self.infinite = infinite

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("tarpit_exponential_delay", client_ip, "K8S_STREAM", "cluster_events")
        try:
            delay = 0.05
            i = 0
            while self.infinite or i < 5:
                await asyncio.sleep(delay)
                writer.write(f"EVENT_{i}: STATUS_PENDING (next poll in {delay*2:.2f}s)\n".encode("utf-8"))
                await writer.drain()
                delay = min(delay * 1.5, 30.0)
                i += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


# =====================================================================
# The 4 Interconnected Tracks
# =====================================================================

class Track1SloppyDeveloper:
    """
    Track 1:
    - Port 22 SSH accepts admin:admin123
    - Fake ~/.bash_history reveals: mysql -u root -p <db_pass>
    - Port 3306 MySQL contains 'users' table with leaked API keys pointing to Port 8080 /debug
    - Port 8080 REST API routes into Tarpit 1 (Infinite Pagination)
    """
    def __init__(self, factory=None):
        from .cred_factory import HoneypotCredentialFactory
        self.factory = factory or HoneypotCredentialFactory()
        self.tarpit = Tarpit1InfinitePagination()
        self.db_pass = self.factory.generate_db_password("mysql")
        self.api_key = self.factory.generate_api_key("internal_core")
        self.dev_pass = "s3cure_db_2024!"

    async def handle_ssh(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("track1_ssh", client_ip, "SSH_AUTH", "admin:admin123")
        try:
            writer.write(b"SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.4\r\n")
            await writer.drain()
            # Fake prompt and bash history breadcrumb
            banner = (
                f"Welcome to Ubuntu 22.04 LTS (GNU/Linux 5.15.0-generic x86_64)\n"
                f"admin@dev-box:~$ cat ~/.bash_history\n"
                f"git clone https://github.com/internal/core-service\n"
                f"mysql -u root -p {self.dev_pass} -h 127.0.0.1\n"
                f"curl http://127.0.0.1:8080/debug\n"
            ).encode("utf-8")
            writer.write(banner)
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_mysql(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("track1_mysql", client_ip, "MYSQL_AUTH", f"root:{self.dev_pass}")
        try:
            writer.write(b"5.7.42-0ubuntu0.22.04.1\n")
            await writer.drain()
            # Feed fake leaked table with dynamically derived canary API key
            data = (
                f"+----+----------+----------------------------------+-------------------------+\n"
                f"| id | username | api_key                          | service                 |\n"
                f"+----+----------+----------------------------------+-------------------------+\n"
                f"|  1 | admin    | {self.api_key:<32} | https://internal:443/   |\n"
                f"|  2 | dev_lead | {self.dev_pass:<32} | cloud-admin-panel:443   |\n"
                f"+----+----------+----------------------------------+-------------------------+\n"
            ).encode("utf-8")
            writer.write(data)
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_rest_debug(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        await self.tarpit.handle_client(reader, writer, client_ip)


class Track2CloudInfrastructure:
    """
    Track 2:
    - Port 443 HTTPS Admin Panel accepts the leaked DB creds from Track 1 (dev_lead:s3cure_db_2024!)
    - Leads to Port 9000 (MinIO/S3 fake buckets)
    - S3 buckets download config.tar.gz and db_dump.sql
    - Backup files reveal credentials for Port 5432 (Postgres canary data) and Redis session keys for Track 3
    - Port 5432 Postgres leads to Tarpit 2 (Delayed Synthetic Dump)
    """
    def __init__(self, factory=None):
        from .cred_factory import HoneypotCredentialFactory
        self.factory = factory or HoneypotCredentialFactory()
        self.tarpit = Tarpit2DelayedSyntheticDump()
        self.s3_key = self.factory.generate_aws_key("s3")
        self.pg_pass = self.factory.generate_db_password("postgres")

    async def handle_https_admin(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("track2_https_admin", client_ip, "HTTPS_POST", "login dev_lead")
        try:
            resp = (
                f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"
                f'{{"auth": "success", "role": "cloud_admin", '
                f'"s3_endpoint": "http://127.0.0.1:9000", "s3_access_key": "{self.s3_key}"}}\n'
            ).encode("utf-8")
            writer.write(resp)
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_s3_minio(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("track2_s3_minio", client_ip, "S3_LIST_BUCKETS", "s3://backups")
        try:
            resp = (
                f"HTTP/1.1 200 OK\r\nContent-Type: application/xml\r\n\r\n"
                f"<ListBucketResult><Contents><Key>config.tar.gz</Key></Contents>"
                f"<Contents><Key>db_dump.sql</Key><Metadata>postgres:5432 user=canary pass={self.pg_pass}</Metadata></Contents>"
                f"<Contents><Key>redis_tokens.env</Key><Metadata>redis://127.0.0.1:6379</Metadata></Contents>"
                f"</ListBucketResult>\n"
            ).encode("utf-8")
            writer.write(resp)
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_postgres(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        await self.tarpit.handle_client(reader, writer, client_ip)


class Track3IoTInternalNetwork:
    """
    Track 3:
    - Port 80 Router OpenWRT UI (accepts default admin:password)
    - Points to Port 6379 (Redis: No Auth)
    - Redis keys hold session tokens pointing to Port 27017 (MongoDB PII collections)
    - Port 27017 routes into Tarpit 3 (Ever-growing query result stream)
    """
    def __init__(self, factory=None):
        from .cred_factory import HoneypotCredentialFactory
        self.factory = factory or HoneypotCredentialFactory()
        self.tarpit = Tarpit3EverGrowingStream()
        self.redis_token = self.factory.generate_bearer_token("redis_session")

    async def handle_openwrt_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("track3_openwrt", client_ip, "HTTP_GET", "LuCI OpenWRT admin:password")
        try:
            resp = (
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
                b"<html><head><title>OpenWrt - LuCI</title></head>"
                b"<body><h1>OpenWrt Administration</h1>"
                b"<p>Internal Services: Redis Cache at 127.0.0.1:6379 (Unprotected)</p>"
                b"</body></html>\n"
            )
            writer.write(resp)
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_redis(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("track3_redis", client_ip, "REDIS_KEYS", "*")
        try:
            resp = (
                f"*2\r\n$25\r\nsession:{self.redis_token[:15]}\r\n"
                f"$36\r\nmongodb://127.0.0.1:27017/users_pii\r\n"
            ).encode("utf-8")
            writer.write(resp)
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_mongodb(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        await self.tarpit.handle_client(reader, writer, client_ip)


class Track4ExposedManagement:
    """
    Track 4:
    - Port 5900 VNC Desktop (desktop terminal shows Docker commands)
    - Port 2375 Docker Socket API (unauthenticated container inspect)
    - Fake containers hold K8s tokens
    - Port 8443 K8s Dashboard routes into Tarpit 4 (Exponential delay generator)
    """
    def __init__(self, factory=None):
        from .cred_factory import HoneypotCredentialFactory
        self.factory = factory or HoneypotCredentialFactory()
        self.tarpit = Tarpit4ExponentialDelay()
        self.k8s_token = self.factory.generate_bearer_token("k8s_admin")

    async def handle_vnc(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("track4_vnc", client_ip, "RFB_HANDSHAKE", "RFB 003.008")
        try:
            writer.write(b"RFB 003.008\n")
            await writer.drain()
            # Fake VNC header sending banner referencing docker.sock:2375
            banner = b"VNC SCREENSHOT: docker -H tcp://127.0.0.1:2375 ps\n"
            writer.write(banner)
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_docker_api(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        log_honeypot_forensic("track4_docker", client_ip, "DOCKER_CONTAINERS_JSON", "GET /containers/json")
        try:
            resp = (
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"
                b"[{\"Id\": \"k8s_control_plane\", \"Names\": [\"/k8s_manager\"], "
                b"\"Env\": [\"K8S_DASHBOARD=https://127.0.0.1:8443\", "
                b"\"SERVICE_TOKEN=eyJhbGciOiJIUzI1NiJ9.fake_k8s_token\"]}]\n"
            )
            writer.write(resp)
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_k8s_dashboard(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, client_ip: str):
        await self.tarpit.handle_client(reader, writer, client_ip)
