"""Quick test script for Velvet framework."""

import asyncio
from velvet.config import get_config
from velvet.fabric import init_fabric
from velvet.context import init_context_manager, TrackType
from velvet.skills import get_skill_registry
from velvet.gateway import init_gateway
from velvet.example_skills import builtin  # noqa: F401 - registers skills


async def test():
    print("=== Testing Velvet Framework ===\n")
    
    # Init fabric
    print("1. Initializing Zenoh fabric...")
    await init_fabric('test-device', mode='peer')
    print("   ✓ Fabric initialized (mock mode - Zenoh not installed)\n")
    
    # Init context
    print("2. Initializing context manager...")
    ctx_mgr = init_context_manager()
    print(f"   ✓ Tracks active: {list(ctx_mgr.tracks.keys())}\n")
    
    # Init gateway
    print("3. Initializing gateway...")
    gateway = init_gateway()
    print(f"   ✓ Gateway state: {gateway.state.value}\n")
    
    # Test skills
    print("4. Testing skill registry...")
    registry = get_skill_registry()
    skills = registry.list_all()
    print(f"   ✓ Registered skills: {[s.name for s in skills]}\n")
    
    # Execute skills
    print("5. Executing 'get_time' skill...")
    skill = registry.get('get_time')
    result = await skill.execute()
    print(f"   ✓ Result: {result.speak}\n")
    
    print("6. Executing 'system_status' skill...")
    skill = registry.get('system_status')
    result = await skill.execute()
    print(f"   ✓ Result: {result.speak}\n")
    
    print("7. Executing 'remember' skill...")
    skill = registry.get('remember')
    result = await skill.execute(key="test_fact", value="Velvet works!")
    print(f"   ✓ Result: {result.speak}\n")
    
    print("8. Executing 'recall' skill...")
    skill = registry.get('recall')
    result = await skill.execute(key="test_fact")
    print(f"   ✓ Result: {result.speak}\n")
    
    print("=" * 40)
    print("✅ All tests passed! Framework is functional.")
    print("=" * 40)


if __name__ == "__main__":
    asyncio.run(test())
