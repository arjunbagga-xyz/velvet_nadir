"""
Tartarus: The Cold Memory Archive.

Named after the Greek deep abyss — the subconscious of the Velvet memory system.
Stores low-retention memories that are no longer in the active vector index (Aether)
but should never be deleted. Searchable via SQLite FTS5 (full-text search).

Memories in Tartarus can be promoted back to Aether if queried, creating an organic
memory lifecycle: Hot (Aether) → Warm (Mnemosyne) → Cold (Tartarus) → recalled → Hot.
"""

from __future__ import annotations

import sqlite3
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from loguru import logger


class ColdStore:
    """
    Tartarus — Cold archive for low-retention memories.

    Uses a separate SQLite file with FTS5 for text search.
    No vector embeddings — lightweight, disk-only, zero GPU cost.
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".velvet" / "tartarus.db"
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self._path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock: Optional[asyncio.Lock] = None
        self._init_schema()

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _init_schema(self):
        """Create tables if they don't exist."""
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS cold_memories (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                original_retention REAL DEFAULT 0.0,
                original_importance REAL DEFAULT 0.0,
                archived_at TEXT NOT NULL,
                last_accessed TEXT,
                access_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS sutras (
                id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                version_num INTEGER NOT NULL,
                hash TEXT NOT NULL,
                action TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                PRIMARY KEY (id, hash)
            );

            -- FTS5 full-text search index
            CREATE VIRTUAL TABLE IF NOT EXISTS cold_fts
                USING fts5(text, content='cold_memories', content_rowid='rowid');

            -- Trigger to keep FTS in sync on INSERT
            CREATE TRIGGER IF NOT EXISTS cold_ai AFTER INSERT ON cold_memories BEGIN
                INSERT INTO cold_fts(rowid, text)
                VALUES (new.rowid, new.text);
            END;

            -- Trigger to keep FTS in sync on DELETE
            CREATE TRIGGER IF NOT EXISTS cold_ad AFTER DELETE ON cold_memories BEGIN
                INSERT INTO cold_fts(cold_fts, rowid, text)
                VALUES ('delete', old.rowid, old.text);
            END;
        """)
        self._db.commit()

    def get_version_vector(self) -> dict[str, int]:
        """Get the current version vector (highest version_num per device)."""
        cursor = self._db.execute(
            "SELECT device_id, MAX(version_num) as max_v FROM sutras GROUP BY device_id"
        )
        return {row["device_id"]: row["max_v"] for row in cursor}

    def get_merkle_root(self) -> str:
        """Get the Merkle-like root hash of the causal log."""
        cursor = self._db.execute("SELECT hash FROM sutras ORDER BY device_id, version_num")
        hashes = [row["hash"] for row in cursor]
        if not hashes:
            return "empty"
        combined = "".join(hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    def log_sutra(self, device_id: str, action: str, payload_dict: dict) -> dict:
        """Create and log a new local transaction (sutra)."""
        cursor = self._db.execute(
            "SELECT MAX(version_num) as max_v FROM sutras WHERE device_id = ?",
            (device_id,)
        )
        row = cursor.fetchone()
        next_v = (row["max_v"] or 0) + 1
        
        cursor = self._db.execute(
            "SELECT hash FROM sutras WHERE device_id = ? AND version_num = ?",
            (device_id, next_v - 1)
        )
        prev_row = cursor.fetchone()
        prev_hash = prev_row["hash"] if prev_row else "genesis"
        
        payload_str = json.dumps(payload_dict)
        now = datetime.now(timezone.utc).isoformat()
        
        hash_input = f"{prev_hash}:{device_id}:{next_v}:{action}:{payload_str}:{now}"
        sutra_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        sutra_id = f"{device_id}:{next_v}"
        
        self._db.execute(
            """INSERT INTO sutras (id, device_id, version_num, hash, action, payload, timestamp, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')""",
            (sutra_id, device_id, next_v, sutra_hash, action, payload_str, now)
        )
        self._db.commit()
        return {
            "id": sutra_id,
            "device_id": device_id,
            "version_num": next_v,
            "hash": sutra_hash,
            "action": action,
            "payload": payload_dict,
            "timestamp": now,
            "status": "ACTIVE"
        }

    def get_sutras_since(self, version_vector: dict[str, int]) -> list[dict]:
        """Get all sutras that have version numbers higher than specified in the vector."""
        all_sutras = []
        cursor = self._db.execute("SELECT DISTINCT device_id FROM sutras")
        devices = [row["device_id"] for row in cursor]
        
        for dev in devices:
            since_v = version_vector.get(dev, 0)
            cursor = self._db.execute(
                """SELECT id, device_id, version_num, hash, action, payload, timestamp, status
                   FROM sutras WHERE device_id = ? AND version_num > ? ORDER BY version_num""",
                (dev, since_v)
            )
            for row in cursor:
                all_sutras.append({
                    "id": row["id"],
                    "device_id": row["device_id"],
                    "version_num": row["version_num"],
                    "hash": row["hash"],
                    "action": row["action"],
                    "payload": json.loads(row["payload"]),
                    "timestamp": row["timestamp"],
                    "status": row["status"]
                })
        return all_sutras

    def replicate_sutra(self, sutra: dict) -> bool:
        """Insert a replicated sutra from a peer. Marks conflict status if concurrent version."""
        sutra_id = sutra["id"]
        device_id = sutra["device_id"]
        version_num = sutra["version_num"]
        
        cursor = self._db.execute("SELECT id, hash FROM sutras WHERE id = ?", (sutra_id,))
        existing = cursor.fetchall()
        if existing:
            if any(row["hash"] == sutra["hash"] for row in existing):
                return False
                
            self._db.execute(
                "UPDATE sutras SET status = 'CONFLICT_UNRESOLVED' WHERE id = ?",
                (sutra_id,)
            )
            self._db.commit()
            logger.warning(f"[Tartarus] Causal log conflict on {sutra_id}")
            status = "CONFLICT_UNRESOLVED"
        else:
            status = sutra.get("status", "ACTIVE")
            
        payload_str = json.dumps(sutra["payload"])
        
        try:
            self._db.execute(
                """INSERT INTO sutras (id, device_id, version_num, hash, action, payload, timestamp, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (sutra_id, device_id, version_num, sutra["hash"], sutra["action"], payload_str, sutra["timestamp"], status)
            )
            self._db.commit()
            return True
        except Exception as e:
            logger.error(f"[Tartarus] Replicate sutra failed: {e}")
            return False

    def store(self, memory_id: str, text: str, role: str = "user",
              retention: float = 0.0, importance: float = 0.0,
              metadata: dict | None = None):
        """Archive a memory into Tartarus."""
        import json
        now = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata or {})

        try:
            self._db.execute(
                """INSERT OR REPLACE INTO cold_memories
                   (id, text, role, original_retention, original_importance,
                    archived_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (memory_id, text, role, retention, importance, now, meta_str)
            )
            self._db.commit()
            logger.debug(f"[Tartarus] Archived memory {memory_id[:8]}...")
        except Exception as e:
            logger.error(f"[Tartarus] Store failed: {e}")

    def search(self, keywords: list[str], limit: int = 5) -> list[dict]:
        """
        Search cold memories using FTS5 full-text search.

        Args:
            keywords: List of search terms (OR'd together).
            limit: Max results.

        Returns:
            List of memory dicts with id, text, role, metadata.
        """
        if not keywords:
            return []

        # Build FTS5 query: OR all keywords
        fts_query = " OR ".join(
            f'"{kw}"' for kw in keywords if kw.strip()
        )
        if not fts_query:
            return []

        try:
            cursor = self._db.execute(
                """SELECT cm.id, cm.text, cm.role, cm.metadata,
                          cm.original_retention, cm.original_importance
                   FROM cold_fts fts
                   JOIN cold_memories cm ON fts.rowid = cm.rowid
                   WHERE cold_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (fts_query, limit)
            )
            results = []
            for row in cursor:
                import json
                results.append({
                    "id": row["id"],
                    "text": row["text"],
                    "role": row["role"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "retention": row["original_retention"],
                    "importance": row["original_importance"],
                })
            return results
        except Exception as e:
            logger.error(f"[Tartarus] Search failed: {e}")
            return []

    def mark_accessed(self, memory_id: str):
        """Mark a cold memory as recently accessed (candidate for promotion)."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._db.execute(
                """UPDATE cold_memories
                   SET last_accessed = ?, access_count = access_count + 1
                   WHERE id = ?""",
                (now, memory_id)
            )
            self._db.commit()
        except Exception as e:
            logger.error(f"[Tartarus] Mark accessed failed: {e}")

    def get_recently_accessed(self, days: int = 7) -> list[dict]:
        """
        Find cold memories accessed recently — candidates for promotion to Aether.

        Returns memories accessed within the last N days.
        """
        from datetime import timedelta
        import json

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        try:
            cursor = self._db.execute(
                """SELECT id, text, role, metadata, original_retention, original_importance
                   FROM cold_memories
                   WHERE last_accessed IS NOT NULL AND last_accessed > ?
                   ORDER BY access_count DESC
                   LIMIT 20""",
                (cutoff,)
            )
            results = []
            for row in cursor:
                results.append({
                    "id": row["id"],
                    "text": row["text"],
                    "role": row["role"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                })
            return results
        except Exception as e:
            logger.error(f"[Tartarus] Get recently accessed failed: {e}")
            return []

    def remove(self, memory_id: str):
        """Remove a memory from cold store (after promotion back to Aether)."""
        try:
            self._db.execute("DELETE FROM cold_memories WHERE id = ?", (memory_id,))
            self._db.commit()
        except Exception as e:
            logger.error(f"[Tartarus] Remove failed: {e}")

    def count(self) -> int:
        """Count total cold memories."""
        try:
            cursor = self._db.execute("SELECT COUNT(*) FROM cold_memories")
            return cursor.fetchone()[0]
        except Exception:
            return 0

    def compact(self):
        """SQLite VACUUM for space reclamation."""
        try:
            self._db.execute("VACUUM")
            logger.debug("[Tartarus] Compacted cold store")
        except Exception as e:
            logger.error(f"[Tartarus] Compact failed: {e}")

    def get_unresolved_conflicts(self) -> list[dict]:
        """Fetch all sutras marked as unresolved conflicts."""
        cursor = self._db.execute(
            """SELECT id, device_id, version_num, hash, action, payload, timestamp, status
               FROM sutras WHERE status = 'CONFLICT_UNRESOLVED'"""
        )
        conflicts = []
        for row in cursor:
            conflicts.append({
                "id": row["id"],
                "device_id": row["device_id"],
                "version_num": row["version_num"],
                "hash": row["hash"],
                "action": row["action"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["timestamp"],
                "status": row["status"]
            })
        return conflicts

    def resolve_conflict(self, sutra_id: str, final_payload: dict) -> None:
        """Mark a conflict as resolved by updating the first record and deleting others."""
        payload_str = json.dumps(final_payload)
        cursor = self._db.execute("SELECT hash FROM sutras WHERE id = ?", (sutra_id,))
        rows = cursor.fetchall()
        if not rows:
            return
            
        keep_hash = rows[0]["hash"]
        self._db.execute(
            "UPDATE sutras SET payload = ?, status = 'ACTIVE' WHERE id = ? AND hash = ?",
            (payload_str, sutra_id, keep_hash)
        )
        
        if len(rows) > 1:
            for row in rows[1:]:
                self._db.execute(
                    "DELETE FROM sutras WHERE id = ? AND hash = ?",
                    (sutra_id, row["hash"])
                )
        self._db.commit()

    def close(self):
        """Close the database connection."""
        try:
            self._db.close()
        except Exception:
            pass
