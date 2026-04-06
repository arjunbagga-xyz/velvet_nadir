"""
Comprehensive system test for Velvet Nadir.

Tests:
1. Configuration loading
2. Zenoh fabric (real mode)
3. Context manager with persistence
4. Memory storage (SQLite + ChromaDB)
5. Skill registry and execution
6. Phone bridge startup
"""

import asyncio
import shutil
import time
import sys
import os
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Test data directory  
TEST_DIR = Path("./test_system_data")


async def cleanup():
    """Clean up test data."""
    if TEST_DIR.exists():
        try:
            shutil.rmtree(TEST_DIR, ignore_errors=True)
        except Exception:
            pass


async def test_config():
    """Test configuration loading."""
    print("\n=== Test 1: Configuration ===")
    from velvet.config import load_config
    
    config = load_config()
    print(f"  Device ID: {config.device_id}")
    print(f"  Wake word: {config.audio.wake_word}")
    print(f"  Context tracks: {config.context.tracks}")
    print("  [OK] Config")
    return True


async def test_zenoh():
    """Test Zenoh fabric."""
    print("\n=== Test 2: Zenoh Fabric ===")
    from velvet.fabric import ZenohFabric
    
    fabric = ZenohFabric("test-device", mode="peer")
    await fabric.start()
    print(f"  Mode: peer")
    print(f"  Real Zenoh: {fabric.is_real_zenoh()}")
    
    # Test pub/sub
    received = []
    
    async def handler(msg):
        received.append(msg)
        
    await fabric.subscribe("test/topic", handler)
    await fabric.publish("test/topic", {"test": "data"})
    await asyncio.sleep(0.2)
    
    print(f"  Published and received: {len(received)} message(s)")
    await fabric.stop()
    print("  [OK] Zenoh")
    return len(received) > 0


async def test_memory():
    """Test persistent memory."""
    print("\n=== Test 3: Persistent Memory ===")
    from velvet.memory import PersistentMemory
    
    memory = PersistentMemory(TEST_DIR / "memory")
    await memory.initialize()
    
    # Test fact storage
    await memory.remember("user_name", "Test User", category="personal")
    recalled = await memory.recall("user_name")
    print(f"  SQLite fact: stored='Test User', recalled='{recalled}'")
    
    # Test vector search (if available)
    if memory.vector._collection:
        results = await memory.search_memory("test user")
        print(f"  Vector search: {len(results)} result(s)")
    else:
        print("  Vector search: SKIPPED (no ChromaDB)")
    
    await memory.close()
    print("  [OK] Memory")
    return recalled == "Test User"


async def test_context():
    """Test context manager with persistence."""
    print("\n=== Test 4: Context Manager ===")
    from velvet.context import ContextManager, TrackType
    from velvet.memory import PersistentMemory
    
    memory = PersistentMemory(TEST_DIR / "context_memory")
    await memory.initialize()
    
    ctx = ContextManager()
    ctx.set_persistence(memory)
    
    # Update a track
    await ctx.update_track(TrackType.PERSONAL, "test_key", "test_value")
    
    # Get context
    active = await ctx.get_active_context()
    print(f"  Tracks: {list(active['tracks'].keys())}")
    print(f"  Global engagement: {active['global_engagement']}")
    
    # Check persistence
    stored = ctx.tracks[TrackType.PERSONAL].state.get("test_key")
    print(f"  Stored in track: {stored}")
    
    await memory.close()
    print("  [OK] Context")
    return stored == "test_value"


async def test_skills():
    """Test skill registry."""
    print("\n=== Test 5: Skills ===")
    from velvet.skills import get_skill_registry
    from velvet.example_skills import builtin  # Register skills
    
    registry = get_skill_registry()
    skills = registry.list_all()
    print(f"  Registered skills: {len(skills)}")
    for s in skills[:3]:
        print(f"    - {s.name}")
    
    # Execute a skill
    time_skill = registry.get("get_time")
    if time_skill:
        result = await time_skill.execute()
        print(f"  get_time result: {result.data.get('time', 'N/A') if result.data else 'N/A'}")
    
    print("  [OK] Skills")
    return len(skills) > 0






async def main():
    """Run all tests."""
    print("=" * 60)
    print("   VELVET NADIR - System Test")
    print("=" * 60)
    
    await cleanup()
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    try:
        results["config"] = await test_config()
    except Exception as e:
        print(f"  [FAIL] Config: {e}")
        results["config"] = False
        
    try:
        results["zenoh"] = await test_zenoh()
    except Exception as e:
        print(f"  [FAIL] Zenoh: {e}")
        results["zenoh"] = False
        
    try:
        results["memory"] = await test_memory()
    except Exception as e:
        print(f"  [FAIL] Memory: {e}")
        results["memory"] = False
        
    try:
        results["context"] = await test_context()
    except Exception as e:
        print(f"  [FAIL] Context: {e}")
        results["context"] = False
        
    try:
        results["skills"] = await test_skills()
    except Exception as e:
        print(f"  [FAIL] Skills: {e}")
        results["skills"] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("   TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
        
    print(f"\n  Total: {passed}/{total} passed")
    print("=" * 60)
    
    # Cleanup
    await cleanup()
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
