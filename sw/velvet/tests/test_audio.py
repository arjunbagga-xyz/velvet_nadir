"""
Tests for Audio Pipeline.
"""

import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Mock optional audio modules if not installed
try:
    import openwakeword
except ImportError:
    sys.modules["openwakeword"] = MagicMock()
    sys.modules["openwakeword.model"] = MagicMock()

try:
    import faster_whisper
except ImportError:
    sys.modules["faster_whisper"] = MagicMock()

import pytest
import asyncio
from velvet.audio import WakeWordDetector, SpeechToText, AudioCapture

# ============================================================================
# Unit Tests (Mocked)
# ============================================================================

def test_wakeword_load_mock():
    """Test wake word model loading with mocks."""
    with patch("openwakeword.model.Model") as MockModel:
        detector = WakeWordDetector(wake_phrase="hey_jarvis")
        success = detector.load()
        assert success
        assert detector._model is not None
        MockModel.assert_called()

def test_stt_load_mock():
    """Test STT model loading with mocks."""
    with patch("faster_whisper.WhisperModel") as MockWhisper:
        stt = SpeechToText(model_size="tiny")
        success = stt.load()
        assert success
        assert stt._model is not None
        MockWhisper.assert_called()

# ============================================================================
# Integration Tests (Requires Hardware)
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_capture_device():
    """Test actual audio capture from default microphone."""
    try:
        import pyaudio
    except ImportError:
        pytest.skip("pyaudio not installed")

    capture = AudioCapture(sample_rate=16000, chunk_size=1024)
    
    await capture.start()
    try:
        # Read a few chunks
        chunk = await capture.get_chunk(timeout=2.0)
        assert chunk is not None
        assert len(chunk.data) > 0
    finally:
        await capture.stop()
