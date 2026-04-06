"""
Tests for Monitors (AudioMonitor).
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from velvet.monitors import AudioMonitor

@pytest.mark.asyncio
async def test_audio_monitor_start_starts_pipeline():
    """Test that AudioMonitor starts the underlying AudioPipeline."""
    
    # Mock Fabric since monitors use get_fabric()
    with patch("velvet.monitors.get_fabric") as mock_get_fabric:
        # Mock Config since AudioMonitor reads it
        with patch("velvet.config.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.audio.wake_word = "hey velvet"
            mock_config.audio.whisper_model_path = None
            mock_config.audio.tts_model_path = None
            mock_get_config.return_value = mock_config
            
            # Mock AudioPipeline class
            with patch("velvet.audio.AudioPipeline") as MockPipelineClass:
                mock_pipeline_instance = AsyncMock()
                MockPipelineClass.return_value = mock_pipeline_instance
                
                monitor = AudioMonitor()
                await monitor.start()
                
                # Check if AudioPipeline was initialized with correct config
                MockPipelineClass.assert_called_with(
                    wake_word="hey velvet",
                    whisper_model="base",
                    tts_voice="en_US-lessac-medium"
                )
                
                # Check if start was called
                mock_pipeline_instance.start.assert_called_once()
                
                await monitor.stop()
                mock_pipeline_instance.stop.assert_called_once()
