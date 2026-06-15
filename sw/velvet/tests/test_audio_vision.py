import sys
import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock, patch

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

from velvet.audio import WakeWordDetector, SpeechToText
from velvet.monitors import AudioMonitor
from velvet.shen.po import Po
from velvet.skills.vision_skill import look


# ============================================================================
# Audio Pipeline Unit Tests (Mocked)
# ============================================================================

class TestAudioPipeline:
    """Test wake word and STT loaders with mock libraries."""

    def test_wakeword_load_mock(self):
        """Test wake word model loading with mocks."""
        with patch("openwakeword.model.Model") as MockModel:
            detector = WakeWordDetector(wake_phrase="hey_jarvis")
            success = detector.load()
            assert success
            assert detector._model is not None
            MockModel.assert_called()

    def test_stt_load_mock(self):
        """Test STT model loading with mocks."""
        with patch("faster_whisper.WhisperModel") as MockWhisper:
            stt = SpeechToText(model_size="tiny")
            success = stt.load()
            assert success
            assert stt._model is not None
            MockWhisper.assert_called()

    def test_wake_word_config_plumbing(self):
        """AudioPipeline receives custom wake_word and wake_model_path."""
        with patch("velvet.audio.AudioCapture"), \
             patch("velvet.audio.VADProcessor"), \
             patch("velvet.config.get_config") as mock_get_config:
            
            mock_cfg = MagicMock()
            mock_cfg.audio.stt_provider = "whisper"
            mock_get_config.return_value = mock_cfg
            
            from velvet.audio import AudioPipeline
            
            # Test default
            pipeline = AudioPipeline()
            assert pipeline.wake_detector.wake_phrase == "Hey Velvet"
            assert pipeline.wake_detector.model_path == ""
            
            # Test custom
            pipeline = AudioPipeline(wake_word="custom_wake", wake_model_path="/path/to/custom.onnx")
            assert pipeline.wake_detector.wake_phrase == "custom_wake"
            assert pipeline.wake_detector.model_path == "/path/to/custom.onnx"


# ============================================================================
# Audio Monitor Tests
# ============================================================================

class TestAudioMonitor:
    """Test that AudioMonitor starts and stops the pipeline correctly."""

    @pytest.mark.asyncio
    async def test_audio_monitor_lifecycle(self, mock_fabric):
        with patch("velvet.config.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.audio.wake_word = "hey velvet"
            mock_config.audio.wake_model_path = ""
            mock_config.audio.whisper_model_path = None
            mock_config.audio.tts_model_path = None
            mock_get_config.return_value = mock_config
            
            with patch("velvet.audio.AudioPipeline") as MockPipelineClass:
                mock_pipeline_instance = AsyncMock()
                MockPipelineClass.return_value = mock_pipeline_instance
                
                monitor = AudioMonitor()
                await monitor.start()
                
                # Check setup parameters
                MockPipelineClass.assert_called_with(
                    wake_word="hey velvet",
                    wake_model_path="",
                    whisper_model="base",
                    tts_voice="en_US-lessac-medium"
                )
                mock_pipeline_instance.start.assert_called_once()
                
                await monitor.stop()
                mock_pipeline_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_audio_monitor_plumbing(self, mock_fabric):
        with patch("velvet.config.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.audio.wake_word = "custom_wake"
            mock_config.audio.wake_model_path = "/path/to/custom.onnx"
            mock_config.audio.whisper_model_path = "large"
            mock_config.audio.tts_model_path = "piper_voice"
            mock_get_config.return_value = mock_config
            
            with patch("velvet.audio.AudioPipeline") as MockPipelineClass:
                mock_pipeline_instance = AsyncMock()
                MockPipelineClass.return_value = mock_pipeline_instance
                
                monitor = AudioMonitor()
                await monitor.start()
                
                MockPipelineClass.assert_called_with(
                    wake_word="custom_wake",
                    wake_model_path="/path/to/custom.onnx",
                    whisper_model="large",
                    tts_voice="piper_voice"
                )
                await monitor.stop()


# ============================================================================
# Vision and VLM Skill Tests
# ============================================================================

class TestVisionVLM:
    """Test VLM skill execution with mock vision frames."""

    @pytest.mark.asyncio
    async def test_look_skill_calls_vlm(self):
        with patch("velvet.shen.po.get_config") as mock_config_get, \
             patch("velvet.shen.po.VisionEngine"), \
             patch("velvet.shen.po.VisionMonitor._run"), \
             patch("velvet.gateway.get_gateway") as mock_get_gateway:
            
            # Setup config mocks
            mock_config = MagicMock()
            mock_config.llm.vision_model = "moondream"
            mock_config.llm.base_url = "http://localhost:11434"
            mock_config.shen.po_reflex_model = None
            mock_config_get.return_value = mock_config
            
            # Setup Po with fake frame
            po = Po()
            po.vision_monitor.stop()
            fake_frame = np.ones((10, 10, 3), dtype=np.uint8) * 128
            po.vision_monitor._important_frame = fake_frame
            
            # Mock VisionEngine analyze
            po.vision_engine.analyze = AsyncMock(return_value="I see a gray square.")
            
            # Wire Gateway Yi/Po
            mock_gateway = MagicMock()
            mock_gateway.yi.po = po
            mock_get_gateway.return_value = mock_gateway
            
            result = await look()
            
            assert result.success is True
            assert "I see a gray square." in result.speak
            po.vision_engine.analyze.assert_called_once()
