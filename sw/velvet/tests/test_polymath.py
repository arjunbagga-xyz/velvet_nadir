"""
Tests for Polymath Engine Selector.
"""
import pytest
from unittest.mock import MagicMock, patch
from velvet.shen.polymath import Polymath, HardwareType, HardwareProfile, LlamaCppBackend, TensorRTBackend

@pytest.fixture
def mock_platform_windows():
    with patch("platform.system", return_value="Windows"):
        yield

@pytest.fixture
def mock_platform_linux():
    with patch("platform.system", return_value="Linux"):
        yield

def test_polymath_defaults_to_llamacpp_on_windows(mock_platform_windows):
    """
    On standard Windows without explicit NVML config, should fallback to llama.cpp.
    """
    poly = Polymath()
    # Mock profile to ensure CPU only
    poly.profile = HardwareProfile(
        type=HardwareType.CPU_ONLY,
        vram_gb=0,
        ram_gb=16,
        has_cuda=False,
        has_tensorrt=False,
        cpu_cores=4
    )
    
    backend_class = poly.select_backend_class()
    assert backend_class == LlamaCppBackend

def test_polymath_selects_tensorrt_on_jetson(mock_platform_linux):
    """
    If Jetson + TensorRT detected, select TensorRTBackend.
    """
    poly = Polymath()
    # Cheat: manually set profile to Jetson
    poly.profile = HardwareProfile(
        type=HardwareType.JETSON_ORIN,
        vram_gb=32,
        ram_gb=32,
        has_cuda=True,
        has_tensorrt=True, # Critical flag
        cpu_cores=8
    )
    
    backend_class = poly.select_backend_class()
    assert backend_class == TensorRTBackend

def test_polymath_fallback_on_jetson_without_trt(mock_platform_linux):
    """
    If Jetson but NO TensorRT found, fallback to LlamaCpp.
    """
    poly = Polymath()
    poly.profile = HardwareProfile(
        type=HardwareType.JETSON_ORIN,
        vram_gb=32,
        ram_gb=32,
        has_cuda=True,
        has_tensorrt=False, # Missing TRT
        cpu_cores=8
    )
    
    backend_class = poly.select_backend_class()
    assert backend_class == LlamaCppBackend
