import sys
import os

# Ensure sw/velvet is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
import json

try:
    from powermem import create_memory
    from velvet.shen.polymath import get_polymath
    from velvet.config import get_config

    cfg = get_config()
    print("--- Velvet Config Loaded ---")
    print("Embedding model:", cfg.memory.embedding_model)
    print("LLM base URL:", cfg.llm.base_url)
    
    poly = get_polymath()
    config = poly.build_memory_config()
    print("\n--- PowerMem Config Built by Polymath ---")
    print(json.dumps(config, indent=2))
    
    print("\n--- Attempting PowerMem Initialization ---")
    mem = create_memory(config=config, agent_id="velvet")
    print("\nPowerMem successfully created!", mem)
except Exception as e:
    import traceback
    print("\n--- PowerMem Initialization Failed with Traceback ---")
    traceback.print_exc()
