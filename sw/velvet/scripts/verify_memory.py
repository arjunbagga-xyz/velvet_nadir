"""Quick test for memory persistence."""
import asyncio
from pathlib import Path
from velvet.memory import init_memory

async def test():
    m = await init_memory(Path('./test_data'))
    
    # Test fact storage
    await m.remember('test_key', 'test_value')
    r = await m.recall('test_key')
    print(f'SQLite - Stored: test_value, Recalled: {r}')
    
    # Test vector memory
    results = await m.search_memory('test')
    print(f'Vector search returned {len(results)} results')
    
    await m.close()
    print('Memory test: PASSED' if r == 'test_value' else 'Memory test: FAILED')

if __name__ == '__main__':
    asyncio.run(test())
