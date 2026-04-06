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
        self._db = sqlite3.connect(str(self._path))
        self._db.row_factory = sqlite3.Row
        self._init_schema()

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

    def close(self):
        """Close the database connection."""
        try:
            self._db.close()
        except Exception:
            pass
