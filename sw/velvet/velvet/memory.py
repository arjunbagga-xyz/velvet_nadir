"""
Persistent memory system for Velvet Nadir.

Provides:
- Vector storage (ChromaDB) for semantic memory retrieval
- SQLite for structured data (context tracks, conversation history)
- Save/load context state across restarts
"""

__all__ = [
    "VectorMemory",
    "SQLiteStore",
    "PersistentMemory",
    "MemoryAdapterError",
    "get_memory",
    "init_memory",
]

import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
import aiosqlite
from loguru import logger

from velvet.errors import MemoryAdapterError

# ChromaDB import (optional)
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None  # type: ignore


class VectorMemory:
    """
    Vector storage for semantic memory using ChromaDB.
    
    Stores embeddings for:
    - Conversation snippets
    - Remembered facts
    - Documents and notes
    """
    
    def __init__(self, persist_dir: Path):
        self.persist_dir = persist_dir
        self._client = None
        self._collection = None
        
    async def initialize(self) -> bool:
        """Initialize ChromaDB client and collection."""
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not installed, vector memory disabled")
            return False
            
        try:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            
            # Run in executor since ChromaDB is sync
            loop = asyncio.get_running_loop()
            
            def _init():
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_dir),
                    settings=Settings(anonymized_telemetry=False),
                )
                self._collection = self._client.get_or_create_collection(
                    name="velvet_memory",
                    metadata={"hnsw:space": "cosine", "description": "Velvet Nadir long-term memory"}
                )
                return True
                
            result = await loop.run_in_executor(None, _init)
            logger.info(f"Vector memory initialized at {self.persist_dir}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            return False
            
    async def add(
        self,
        text: str,
        memory_id: str,
        metadata: dict | None = None,
        embedding: list[float] | None = None,
    ) -> bool:
        """Add a memory to the vector store."""
        if not self._collection:
            logger.warning(f"Vector memory unavailable — cannot store memory '{memory_id}'. "
                          "Install chromadb: pip install chromadb")
            return False
            
        try:
            loop = asyncio.get_running_loop()
            
            meta = metadata or {}
            meta["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            def _add():
                if embedding:
                    self._collection.add(
                        ids=[memory_id],
                        documents=[text],
                        embeddings=[embedding],
                        metadatas=[meta],
                    )
                else:
                    # ChromaDB will generate embeddings
                    self._collection.add(
                        ids=[memory_id],
                        documents=[text],
                        metadatas=[meta],
                    )
                    
            await loop.run_in_executor(None, _add)
            logger.debug(f"Added memory: {memory_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return False
            
    async def search(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        """Search for similar memories."""
        if not self._collection:
            logger.warning("Vector memory unavailable — search skipped. "
                          "Install chromadb: pip install chromadb")
            return []
            
        try:
            loop = asyncio.get_running_loop()
            
            def _search():
                results = self._collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where,
                )
                return results
                
            results = await loop.run_in_executor(None, _search)
            
            # Format results
            memories = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    memories.append({
                        "id": results["ids"][0][i] if results["ids"] else None,
                        "text": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results.get("distances") else None,
                    })
                    
            return memories
            
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []
            
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        if not self._collection:
            logger.warning(f"Vector memory unavailable — cannot delete '{memory_id}'")
            return False
            
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._collection.delete(ids=[memory_id])
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False


class SQLiteStore:
    """
    SQLite storage for structured data.
    
    Stores:
    - Context track states
    - Conversation history
    - Session metadata
    - User preferences
    """
    
    SCHEMA = """
    -- Context tracks persisted state
    CREATE TABLE IF NOT EXISTS context_tracks (
        track_type TEXT PRIMARY KEY,
        state_json TEXT NOT NULL,
        engagement TEXT NOT NULL DEFAULT 'MONITORING',
        updated_at TEXT NOT NULL
    );
    
    -- Conversation history
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata_json TEXT,
        created_at TEXT NOT NULL
    );
    
    -- Remembered facts (key-value pairs)
    CREATE TABLE IF NOT EXISTS facts (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        category TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    
    -- Session metadata
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        summary TEXT
    );
    
    -- Device scripts for plug-n-play control
    CREATE TABLE IF NOT EXISTS device_scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_type TEXT NOT NULL,
        device_model TEXT NOT NULL,
        action TEXT NOT NULL,
        script TEXT NOT NULL,
        description TEXT,
        verified INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(device_type, device_model, action)
    );
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
    CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at);
    CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
    CREATE INDEX IF NOT EXISTS idx_scripts_device ON device_scripts(device_type, device_model);
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None
        
    async def initialize(self) -> bool:
        """Initialize the database."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self._db = await aiosqlite.connect(str(self.db_path))
            await self._db.executescript(self.SCHEMA)
            await self._db.commit()
            
            logger.info(f"SQLite store initialized at {self.db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            return False
            
    async def close(self):
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            
    # ==================== Context Tracks ====================
    
    async def save_track(self, track_type: str, state: dict, engagement: str) -> bool:
        """Save a context track state."""
        if not self._db:
            return False
            
        try:
            await self._db.execute(
                """
                INSERT OR REPLACE INTO context_tracks (track_type, state_json, engagement, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (track_type, json.dumps(state), engagement, datetime.now(timezone.utc).isoformat())
            )
            await self._db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save track: {e}")
            return False
            
    async def load_track(self, track_type: str) -> dict | None:
        """Load a context track state."""
        if not self._db:
            return None
            
        try:
            async with self._db.execute(
                "SELECT state_json, engagement FROM context_tracks WHERE track_type = ?",
                (track_type,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "state": json.loads(row[0]),
                        "engagement": row[1],
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to load track: {e}")
            return None
            
    async def load_all_tracks(self) -> dict[str, dict]:
        """Load all context track states."""
        if not self._db:
            return {}
            
        try:
            tracks = {}
            async with self._db.execute(
                "SELECT track_type, state_json, engagement FROM context_tracks"
            ) as cursor:
                async for row in cursor:
                    tracks[row[0]] = {
                        "state": json.loads(row[1]),
                        "engagement": row[2],
                    }
            return tracks
        except Exception as e:
            logger.error(f"Failed to load tracks: {e}")
            return {}
            
    # ==================== Conversations ====================
    
    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> bool:
        """Save a conversation message."""
        if not self._db:
            return False
            
        try:
            await self._db.execute(
                """
                INSERT INTO conversations (session_id, role, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, json.dumps(metadata) if metadata else None,
                 datetime.now(timezone.utc).isoformat())
            )
            await self._db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return False
            
    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """Get messages for a session."""
        if not self._db:
            return []
            
        try:
            messages = []
            async with self._db.execute(
                """
                SELECT role, content, metadata_json, created_at
                FROM conversations
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit)
            ) as cursor:
                async for row in cursor:
                    messages.append({
                        "role": row[0],
                        "content": row[1],
                        "metadata": json.loads(row[2]) if row[2] else None,
                        "created_at": row[3],
                    })
            return list(reversed(messages))  # Chronological order
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
            
    # ==================== Facts ====================
    
    async def save_fact(self, key: str, value: str, category: str | None = None) -> bool:
        """Save a fact (key-value pair)."""
        if not self._db:
            return False
            
        try:
            now = datetime.now(timezone.utc).isoformat()
            await self._db.execute(
                """
                INSERT INTO facts (key, value, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, category = ?, updated_at = ?
                """,
                (key, value, category, now, now, value, category, now)
            )
            await self._db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save fact: {e}")
            return False
            
    async def get_fact(self, key: str) -> str | None:
        """Get a fact by key."""
        if not self._db:
            return None
            
        try:
            async with self._db.execute(
                "SELECT value FROM facts WHERE key = ?",
                (key,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get fact: {e}")
            return None
            
    async def get_facts_by_category(self, category: str) -> dict[str, str]:
        """Get all facts in a category."""
        if not self._db:
            return {}
            
        try:
            facts = {}
            async with self._db.execute(
                "SELECT key, value FROM facts WHERE category = ?",
                (category,)
            ) as cursor:
                async for row in cursor:
                    facts[row[0]] = row[1]
            return facts
        except Exception as e:
            logger.error(f"Failed to get facts: {e}")
            return {}
    
    # ==================== Device Scripts ====================
    
    async def save_script(
        self,
        device_type: str,
        device_model: str,
        action: str,
        script: str,
        description: str = "",
        verified: bool = False,
    ) -> bool:
        """Save a device control script."""
        if not self._db:
            return False
            
        try:
            now = datetime.now(timezone.utc).isoformat()
            await self._db.execute(
                """
                INSERT INTO device_scripts (device_type, device_model, action, script, description, verified, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_type, device_model, action) DO UPDATE SET
                    script = ?, description = ?, verified = ?, updated_at = ?
                """,
                (device_type, device_model, action, script, description, 1 if verified else 0, now, now,
                 script, description, 1 if verified else 0, now)
            )
            await self._db.commit()
            logger.debug(f"Saved script: {device_type}/{device_model}/{action}")
            return True
        except Exception as e:
            logger.error(f"Failed to save script: {e}")
            return False
    
    async def get_script(
        self,
        device_type: str,
        device_model: str,
        action: str,
    ) -> dict | None:
        """Get a specific device script."""
        if not self._db:
            return None
            
        try:
            async with self._db.execute(
                """SELECT script, description, verified FROM device_scripts
                   WHERE device_type = ? AND device_model = ? AND action = ?""",
                (device_type, device_model, action)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "script": row[0],
                        "description": row[1],
                        "verified": bool(row[2]),
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to get script: {e}")
            return None
    
    async def get_device_scripts(
        self,
        device_type: str,
        device_model: str,
    ) -> list[dict]:
        """Get all scripts for a device type/model."""
        if not self._db:
            return []
            
        try:
            scripts = []
            async with self._db.execute(
                """SELECT action, script, description, verified FROM device_scripts
                   WHERE device_type = ? AND device_model = ?""",
                (device_type, device_model)
            ) as cursor:
                async for row in cursor:
                    scripts.append({
                        "action": row[0],
                        "script": row[1],
                        "description": row[2],
                        "verified": bool(row[3]),
                    })
            return scripts
        except Exception as e:
            logger.error(f"Failed to get device scripts: {e}")
            return []
    
    async def find_scripts_by_action(self, action: str) -> list[dict]:
        """Find all scripts for a given action across device types."""
        if not self._db:
            return []
            
        try:
            scripts = []
            async with self._db.execute(
                """SELECT device_type, device_model, script, description, verified 
                   FROM device_scripts WHERE action = ?""",
                (action,)
            ) as cursor:
                async for row in cursor:
                    scripts.append({
                        "device_type": row[0],
                        "device_model": row[1],
                        "script": row[2],
                        "description": row[3],
                        "verified": bool(row[4]),
                    })
            return scripts
        except Exception as e:
            logger.error(f"Failed to find scripts: {e}")
            return []


class PersistentMemory:
    """
    Combined persistent memory system.
    
    Integrates vector storage and SQLite for complete memory persistence.
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.vector = VectorMemory(data_dir / "vector_db")
        self.store = SQLiteStore(data_dir / "velvet.db")
        self._initialized = False
        
    async def initialize(self) -> bool:
        """Initialize all storage backends."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        sqlite_ok = await self.store.initialize()
        vector_ok = await self.vector.initialize()
        
        self._initialized = sqlite_ok  # Vector is optional
        
        if self._initialized:
            vector_status = "active" if vector_ok else "unavailable (install chromadb)"
            logger.info(f"Persistent memory initialized — SQLite: active, Vector: {vector_status}")
        else:
            logger.error("Persistent memory initialization failed — SQLite unavailable")
            
        return self._initialized
        
    async def close(self):
        """Close all storage connections."""
        await self.store.close()
        
    def is_ready(self) -> bool:
        """Check if memory is initialized and ready."""
        return self._initialized
        
    # ==================== High-level API ====================
    
    async def remember(self, key: str, value: str, category: str = "general") -> bool:
        """Remember a fact with optional vector indexing."""
        # Store in SQLite
        success = await self.store.save_fact(key, value, category)
        
        # Also add to vector store for semantic search
        if success and self.vector._collection:
            await self.vector.add(
                text=f"{key}: {value}",
                memory_id=f"fact:{key}",
                metadata={"type": "fact", "key": key, "category": category},
            )
            
        return success
        
    async def recall(self, key: str) -> str | None:
        """Recall a fact by exact key."""
        return await self.store.get_fact(key)
        
    async def search_memory(self, query: str, n_results: int = 5) -> list[dict]:
        """Search memories semantically."""
        return await self.vector.search(query, n_results)


# Singleton instance
_memory: PersistentMemory | None = None


def get_memory() -> PersistentMemory:
    """Get the global memory instance."""
    if _memory is None:
        raise MemoryAdapterError("Memory not initialized. Call init_memory() first.")
    return _memory


async def init_memory(data_dir: Path) -> PersistentMemory:
    """Initialize the global memory instance."""
    global _memory
    _memory = PersistentMemory(data_dir)
    await _memory.initialize()
    return _memory
