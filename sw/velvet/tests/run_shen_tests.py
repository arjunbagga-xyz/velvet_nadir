
import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

# Add project root to path
sys.path.append(".")

from velvet.shen.yi import Yi
from velvet.shen.polymath import InferenceBackend

async def run_tests():
    print("Starting Shen Services Verification...")
    
    # 1. Setup Mocks
    print("[Setup] Mocking Config and Polymath...")
    
    # Mock Config
    mock_conf = MagicMock()
    
    # Create mock paths
    mock_reflex_path = MagicMock(spec=Path)
    mock_reflex_path.exists.return_value = True
    mock_reflex_path.__str__.return_value = "fake/reflex.gguf"
    mock_conf.shen.po_reflex_model = mock_reflex_path

    mock_reasoning_path = MagicMock(spec=Path)
    mock_reasoning_path.exists.return_value = True
    mock_reasoning_path.__str__.return_value = "fake/reasoning.gguf"
    mock_conf.shen.hun_reasoning_model = mock_reasoning_path

    # Mock Backends
    reflex_backend = AsyncMock(spec=InferenceBackend)
    reflex_backend.generate.return_value = "Reflex Action Triggered"
    
    reason_backend = AsyncMock(spec=InferenceBackend)
    reason_backend.generate.return_value = "Deep Thought Computed"
    
    def create_backend_side_effect(path, **kwargs):
        if "reflex" in str(path):
            return reflex_backend
        if "reasoning" in str(path):
            return reason_backend
        return MagicMock()

    mock_poly_instance = MagicMock()
    mock_poly_instance.create_backend.side_effect = create_backend_side_effect

    # Mock Jing
    mock_jing_instance = AsyncMock()
    mock_jing_instance.recall.return_value = ["Previous context"]

    # Apply Patches
    with patch("velvet.shen.po.get_config", return_value=mock_conf), \
         patch("velvet.shen.hun.get_config", return_value=mock_conf), \
         patch("velvet.shen.yi.get_config", return_value=mock_conf), \
         patch("velvet.shen.po.Polymath", return_value=mock_poly_instance), \
         patch("velvet.shen.hun.Polymath", return_value=mock_poly_instance), \
         patch("velvet.shen.yi.Jing", return_value=mock_jing_instance):

        # 2. Run Tests
        print("[Test] Initializing Yi...")
        yi = Yi()
        
        # Test 1: Reflex
        print("[Test 1] Dispatching 'turn on lights'...")
        res1 = await yi.dispatch("turn on lights")
        print(f"Result: {res1}")
        assert "Reflex" in res1
        print("-> PASS")

        # Test 2: Reasoning
        print("[Test 2] Dispatching complex query...")
        res2 = await yi.dispatch("explain the theory of relativity and how it relates to time dilation")
        print(f"Result: {res2}")
        assert "Deep Thought" in res2
        print("-> PASS")

    print("\nALL SCENARIOS PASSED.")

if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
