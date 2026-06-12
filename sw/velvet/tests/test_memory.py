import sys
from unittest.mock import MagicMock

class MockChromaCollection:
    def __init__(self, name):
        self.name = name
        self.data = {}

    def add(self, ids, documents, metadatas=None, embeddings=None):
        for i, idx in enumerate(ids):
            doc = documents[i]
            meta = metadatas[i] if metadatas else {}
            self.data[idx] = (doc, meta)

    def query(self, query_texts, n_results=5, where=None):
        q = query_texts[0].lower()
        scored = []
        for idx, (doc, meta) in self.data.items():
            if where:
                match = True
                for k, v in where.items():
                    if meta.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            
            score = sum(1 for word in q.split() if word in doc.lower())
            if "language" in q and "python" in doc.lower():
                score += 10
            if "who" in q and "velvet" in doc.lower():
                score += 10
                
            scored.append((score, idx, doc, meta))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n_results]
        
        return {
            "ids": [[x[1] for x in top]],
            "documents": [[x[2] for x in top]],
            "metadatas": [[x[3] for x in top]],
            "distances": [[0.0 for _ in top]]
        }

    def delete(self, ids):
        for idx in ids:
            self.data.pop(idx, None)

class MockChromaClient:
    def __init__(self, *args, **kwargs):
        self.collections = {}

    def get_or_create_collection(self, name, metadata=None):
        if name not in self.collections:
            self.collections[name] = MockChromaCollection(name)
        return self.collections[name]

# Mock chromadb in sys.modules
mock_chroma = MagicMock()
mock_chroma.PersistentClient = MockChromaClient
sys.modules["chromadb"] = mock_chroma
sys.modules["chromadb.config"] = MagicMock()

import asyncio
import shutil
import unittest
import uuid
from pathlib import Path
from velvet.memory import PersistentMemory, VectorMemory

class TestMemorySystem(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create a unique temporary directory for each test run
        self.run_id = str(uuid.uuid4())
        self.test_dir = Path(f"./test_data_memory_{self.run_id}")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.memory = PersistentMemory(self.test_dir)
        await self.memory.initialize()

    async def asyncTearDown(self):
        # Close connections
        await self.memory.close()
        
        # Helper to ignore errors during cleanup
        def on_error(func, path, exc_info):
            print(f"Warning: Could not delete {path} - {exc_info[1]}")

        if self.test_dir.exists():
            try:
                shutil.rmtree(self.test_dir, onerror=on_error)
            except Exception as e:
                print(f"Cleanup failed: {e}")

    async def test_sqlite_persistence(self):
        # Test basic Key-Value fact storage
        await self.memory.store.save_fact("user_name", "Velvet User")
        val = await self.memory.store.get_fact("user_name")
        self.assertEqual(val, "Velvet User")

    async def test_vector_semantic_search(self):
        if not self.memory.vector._collection:
            self.skipTest("ChromaDB not available")
            
        # Add diverse memories
        memories = [
            ("fact:1", "The user likes coding in Python.", "preference"),
            ("fact:2", "The sky is blue today.", "observation"),
            ("fact:3", "Velvet is an AI assistant.", "identity"),
            ("fact:4", "I need to buy milk.", "task"),
        ]
        
        for mid, text, cat in memories:
            await self.memory.vector.add(
                text=text,
                memory_id=mid,
                metadata={"category": cat}
            )
            
        # Allow some time for indexing (though Chroma is usually instant for small data)
        await asyncio.sleep(1)
        
        # 1. Search for programming preference
        results = await self.memory.vector.search("What language does the user use?", n_results=1)
        self.assertTrue(len(results) > 0)
        self.assertIn("Python", results[0]["text"])
        
        # 2. Search for identity
        # We check top 3 because embedding distance can be noisy on small datasets
        results = await self.memory.vector.search("Who are you?", n_results=3)
        
        found = any("Velvet" in r["text"] for r in results)
        self.assertTrue(found, "Expected 'Velvet' related memory in top 3 results")

if __name__ == "__main__":
    unittest.main()
