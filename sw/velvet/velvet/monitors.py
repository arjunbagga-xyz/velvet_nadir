"""
Stream monitors for Velvet Nadir.

Lightweight, always-on monitors that detect wake events:
- Wake word detection (e.g., "Hey Velvet")
- Voice Activity Detection (VAD)
- Speech-to-Text
- Vision change detection
"""

__all__ = [
    "StreamMonitor",
    "MockAudioMonitor",
    "MockTTSOutput",
    "AudioMonitor",
    "RealTTSOutput",
]

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator
from loguru import logger

from .fabric import get_fabric, MessageType


class StreamMonitor(ABC):
    """Base class for stream monitors."""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._running = False
        self._task: asyncio.Task | None = None
        
    async def start(self) -> None:
        """Start the monitor."""
        if not self.enabled:
            logger.info(f"{self.__class__.__name__} is disabled")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"{self.__class__.__name__} started")
        
    async def stop(self) -> None:
        """Stop the monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"{self.__class__.__name__} stopped")
        
    @abstractmethod
    async def _monitor_loop(self) -> None:
        """Main monitoring loop - override in subclasses."""
        pass


class MockAudioMonitor(StreamMonitor):
    """
    Mock audio monitor for testing without real audio hardware.
    
    Simulates wake word and speech events via fabric messages.
    In production, replace with real audio processing.
    """
    
    async def _monitor_loop(self) -> None:
        """Listen for simulated audio events from console input."""
        fabric = get_fabric()
        
        while self._running:
            try:
                # In production: process actual audio stream
                # For now: just keep running
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audio monitor error: {e}")
                await asyncio.sleep(1)
                
    async def simulate_wake_word(self) -> None:
        """Simulate wake word detection (for testing)."""
        fabric = get_fabric()
        await fabric.publish(
            MessageType.WAKE_WORD.value,
            {"phrase": "hey velvet", "confidence": 0.95}
        )
        
    async def simulate_transcript(self, text: str, is_final: bool = True) -> None:
        """Simulate speech transcript (for testing)."""
        fabric = get_fabric()
        await fabric.publish(
            MessageType.TRANSCRIPT.value,
            {"text": text, "is_final": is_final}
        )


# Obsolete monitors removed in favor of Unified AudioMonitor



class MockTTSOutput:
    """
    Mock TTS output for testing without real audio.
    
    In production, replace with Piper or Coqui XTTS.
    """
    
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        
    async def start(self) -> None:
        """Start listening for TTS requests."""
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("Mock TTS output started")
        
    async def stop(self) -> None:
        """Stop the TTS handler."""
        self._running = False
        if self._task:
            self._task.cancel()
            
    async def _listen_loop(self) -> None:
        """Listen for TTS requests from fabric."""
        fabric = get_fabric()
        
        async def handle_tts(msg):
            text = msg.payload.get("text", "")
            logger.info(f"[TTS OUTPUT] 🔊 {text}")
            # Signal completion
            await fabric.publish(MessageType.TTS_DONE.value, {"text": text})
            
        await fabric.subscribe(MessageType.TTS_SPEAK.value, handle_tts)
        
        while self._running:
            await asyncio.sleep(0.1)


class AudioMonitor(StreamMonitor):
    """
    Unified Audio Monitor wrapping the robust AudioPipeline from velvet.audio.
    
    Features:
    - Wake Word Detection (OpenWakeWord)
    - Voice Activity Detection (Silero VAD)
    - Speech-to-Text (Faster-Whisper)
    - Fabric Integration
    """
    
    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        from .config import get_config
        self._audio_config = get_config().audio
        self._pipeline = None
    
    async def start(self) -> None:
        """Start the audio pipeline."""
        if not self.enabled:
            return
            
        from .audio import AudioPipeline
        
        cfg = self._audio_config
        self._pipeline = AudioPipeline(
            wake_word=cfg.wake_word,
            wake_model_path=getattr(cfg, 'wake_model_path', ''),
            whisper_model=cfg.whisper_model_path or "base",
            tts_voice=cfg.tts_model_path or "en_US-lessac-medium"
        )
        
        # AudioPipeline handles its own async loop and fabric publishing
        await self._pipeline.start()
        
        self._running = True
        logger.info("AudioMonitor started (wrapping AudioPipeline)")
        
    async def stop(self) -> None:
        """Stop the audio pipeline."""
        self._running = False
        if self._pipeline:
            await self._pipeline.stop()
        logger.info("AudioMonitor stopped")
        
    async def _monitor_loop(self) -> None:
        # AudioPipeline has its own loop, so we just wait here
        # or we could rely on the base class behavior. 
        # The base class creates a task for _monitor_loop.
        # Since AudioPipeline runs on its own, we just keep this task alive.
        while self._running:
            await asyncio.sleep(1)


class RealTTSOutput:
    """
    Real TTS output using Piper.
    
    Subscribes to TTS_SPEAK fabric messages and speaks them
    through the audio output device.
    """
    
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._tts = None
    
    async def start(self) -> None:
        """Start listening for TTS requests."""
        from .config import get_config
        from .audio import TextToSpeech
        
        cfg = get_config().audio
        self._tts = TextToSpeech(model_path=cfg.tts_model_path)
        
        if not self._tts.load():
            logger.warning("TTS model failed to load, falling back to console output")
            self._tts = None
        
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("Real TTS output started")
    
    async def stop(self) -> None:
        """Stop the TTS handler."""
        self._running = False
        if self._task:
            self._task.cancel()
    
    async def _listen_loop(self) -> None:
        """Listen for TTS requests from fabric and speak them."""
        fabric = get_fabric()
        
        async def handle_tts(msg):
            text = msg.payload.get("text", "")
            if not text:
                return
            
            if self._tts:
                logger.info(f"[TTS] 🔊 Speaking: {text[:60]}...")
                await self._tts.speak_to_device(text)
            else:
                # Fallback to console
                logger.info(f"[TTS OUTPUT] 🔊 {text}")
            
            # Signal playback completion
            await fabric.publish(MessageType.TTS_DONE.value, {"text": text})
        
        await fabric.subscribe(MessageType.TTS_SPEAK.value, handle_tts)
        
        while self._running:
            await asyncio.sleep(0.1)

