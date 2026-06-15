"""
Real audio pipeline for Velvet Nadir.

Provides:
- Microphone capture with PyAudio
- Voice Activity Detection with Silero VAD
- Wake word detection with OpenWakeWord
- Speech-to-Text with Faster-Whisper
- Text-to-Speech with Piper

All components are optional and gracefully degrade.
"""

__all__ = [
    "SAMPLE_RATE",
    "CHANNELS",
    "CHUNK_SIZE",
    "AudioChunk",
    "AudioCapture",
    "VADProcessor",
    "WakeWordDetector",
    "SpeechToText",
    "AudioOutputStream",
    "TextToSpeech",
    "AudioPipeline",
]

import asyncio
import queue
import threading
import wave
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Awaitable
from loguru import logger

from .fabric import get_fabric, MessageType


# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 512  # ~32ms at 16kHz


@dataclass
class AudioChunk:
    """A chunk of audio data."""
    data: bytes
    sample_rate: int = SAMPLE_RATE
    channels: int = CHANNELS


class AudioCapture:
    """
    Captures audio from the default microphone.
    
    Runs in a background thread to avoid blocking the event loop.
    Pushes audio chunks to an asyncio queue for processing.
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE, chunk_size: int = CHUNK_SIZE):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._running = False
        self._thread: threading.Thread | None = None
        self._queue: asyncio.Queue[AudioChunk] = asyncio.Queue(maxsize=100)
        self._loop: asyncio.AbstractEventLoop | None = None
        
    async def start(self) -> None:
        """Start capturing audio."""
        self._loop = asyncio.get_running_loop()
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Audio capture started")
        
    async def stop(self) -> None:
        """Stop capturing audio."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Audio capture stopped")
        
    def _capture_loop(self) -> None:
        """Background thread for audio capture."""
        try:
            import pyaudio
            
            pa = pyaudio.PyAudio()
            stream = pa.open(
                rate=self.sample_rate,
                channels=CHANNELS,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.chunk_size,
            )
            
            logger.info(f"Microphone opened: {self.sample_rate}Hz, chunk={self.chunk_size}")
            
            while self._running:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    chunk = AudioChunk(data=data, sample_rate=self.sample_rate)
                    
                    # Push to async queue
                    if self._loop:
                        self._loop.call_soon_threadsafe(
                            lambda c=chunk: self._queue.put_nowait(c) if not self._queue.full() else None
                        )
                except Exception as e:
                    logger.error(f"Audio read error: {e}")
                    
            stream.stop_stream()
            stream.close()
            pa.terminate()
            
        except ImportError:
            logger.error("PyAudio not installed. Run: pip install pyaudio")
        except Exception as e:
            logger.error(f"Audio capture error: {e}")
            
    async def get_chunk(self, timeout: float = 1.0) -> AudioChunk | None:
        """Get the next audio chunk."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class VADProcessor:
    """
    Voice Activity Detection using Silero VAD.
    
    Detects when speech starts and ends to segment audio.
    """
    
    def __init__(self, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 1000):
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self._model = None
        self._is_speaking = False
        self._speech_buffer: list[bytes] = []
        self._silence_chunks = 0
        
    def load(self) -> bool:
        """Load the VAD model."""
        try:
            import torch
            
            self._model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True,
            )
            self._get_speech_ts = utils[0]
            logger.info("Silero VAD loaded")
            return True
        except Exception as e:
            logger.warning(f"Could not load Silero VAD: {e}")
            return False
            
    def process_chunk(self, chunk: AudioChunk) -> tuple[bool, bytes | None]:
        """
        Process an audio chunk and detect speech.
        
        Returns:
            (is_speech, completed_speech_audio)
            - is_speech: True if this chunk contains speech
            - completed_speech_audio: Full speech audio when speech ends, else None
        """
        if not self._model:
            # No VAD, pass through everything
            return True, None
            
        try:
            import torch
            import numpy as np
            
            # Convert bytes to tensor
            audio = np.frombuffer(chunk.data, dtype=np.int16).astype(np.float32) / 32768.0
            audio_tensor = torch.from_numpy(audio)
            
            # Get speech probability
            speech_prob = self._model(audio_tensor, SAMPLE_RATE).item()
            is_speech = speech_prob > self.threshold
            
            if is_speech:
                self._speech_buffer.append(chunk.data)
                self._silence_chunks = 0
                
                if not self._is_speaking:
                    self._is_speaking = True
                    logger.debug("Speech started")
                    
                return True, None
            else:
                if self._is_speaking:
                    self._silence_chunks += 1
                    silence_ms = (self._silence_chunks * CHUNK_SIZE * 1000) // SAMPLE_RATE
                    
                    if silence_ms >= self.min_silence_ms:
                        # Speech ended
                        self._is_speaking = False
                        completed = b''.join(self._speech_buffer)
                        self._speech_buffer = []
                        logger.debug(f"Speech ended: {len(completed)} bytes")
                        return False, completed
                    else:
                        # Still in possible pause
                        self._speech_buffer.append(chunk.data)
                        return True, None
                        
                return False, None
                
        except Exception as e:
            logger.error(f"VAD error: {e}")
            return True, None


class WakeWordDetector:
    """
    Wake word detection using OpenWakeWord.
    
    Listens for "Hey Velvet" (or custom phrase).
    """
    
    def __init__(self, wake_phrase: str = "hey_jarvis", threshold: float = 0.5, model_path: str = ""):
        self.wake_phrase = wake_phrase
        self.threshold = threshold
        self.model_path = model_path
        self._model = None
        self._cooldown_until = 0
        
    def load(self) -> bool:
        """Load the wake word model."""
        try:
            from openwakeword.model import Model
            
            # Auto-detect best framework via import cascade (no platform.system())
            try:
                import tflite_runtime  # noqa: F401
                fw = "tflite"
            except ImportError:
                fw = "onnx"  # Universal fallback
            
            if self.model_path:
                # Load from explicit file path
                model_file = Path(self.model_path)
                if not model_file.exists():
                    logger.error(f"Wake word model not found: {model_file}")
                    return False
                self._model = Model(
                    wakeword_models=[str(model_file)],
                    inference_framework=fw,
                )
                logger.info(f"Wake word model loaded from: {model_file}")
            else:
                # Use built-in model by name
                self._model = Model(
                    wakeword_models=[self.wake_phrase],
                    inference_framework=fw,
                )
                logger.info(f"Wake word model loaded: {self.wake_phrase} ({fw})")
            return True
        except Exception as e:
            logger.warning(f"Could not load OpenWakeWord: {e}")
            return False
            
    def process_chunk(self, chunk: AudioChunk) -> tuple[bool, float]:
        """
        Check if chunk contains wake word.
        
        Returns:
            (detected, confidence)
        """
        import time
        
        if not self._model:
            return False, 0.0
            
        # Cooldown to prevent rapid re-triggers
        if time.time() < self._cooldown_until:
            return False, 0.0
            
        try:
            import numpy as np
            
            audio = np.frombuffer(chunk.data, dtype=np.int16)
            predictions = self._model.predict(audio)
            
            for name, score in predictions.items():
                if score > self.threshold:
                    logger.info(f"Wake word detected: {name} ({score:.2f})")
                    self._cooldown_until = time.time() + 2.0  # 2 second cooldown
                    return True, score
                    
            return False, 0.0
            
        except Exception as e:
            logger.error(f"Wake word error: {e}")
            return False, 0.0


class SpeechToText:
    """
    Speech-to-Text using Faster-Whisper.
    """
    
    def __init__(self, model_size: str = "base", device: str = "auto", model_path: str = ""):
        self.model_size = model_size
        self.device = device
        self.model_path = model_path
        self._model = None
        
    def load(self) -> bool:
        """Load the Whisper model."""
        try:
            from faster_whisper import WhisperModel
            
            # Determine device
            device = self.device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
                    
            compute_type = "float16" if device == "cuda" else "int8"
            
            # Use explicit path or model size name
            model_id = self.model_path if self.model_path else self.model_size
            if self.model_path:
                model_file = Path(self.model_path)
                if not model_file.exists():
                    logger.error(f"Whisper model not found: {model_file}")
                    return False
                logger.info(f"Loading Whisper from {model_file} on {device}...")
            else:
                logger.info(f"Loading Whisper {self.model_size} on {device}...")
            
            self._model = WhisperModel(model_id, device=device, compute_type=compute_type)
            logger.info("Whisper model loaded")
            return True
            
        except Exception as e:
            logger.warning(f"Could not load Faster-Whisper: {e}")
            return False
            
    async def transcribe(self, audio_data: bytes, sample_rate: int = SAMPLE_RATE) -> str:
        """Transcribe audio data to text."""
        if not self._model:
            return ""
            
        try:
            # Save to temp file (Whisper needs a file path)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                
            # Write WAV file
            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
                
            # Transcribe in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            segments, info = await loop.run_in_executor(
                None,
                lambda: self._model.transcribe(temp_path, beam_size=5)
            )
            
            # Collect text
            text = " ".join(segment.text.strip() for segment in segments)
            
            # Cleanup
            os.unlink(temp_path)
            
            return text
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""


class AudioOutputStream:
    """
    Universal audio playback via PyAudio.
    Works on all platforms — no winsound, aplay, or os.startfile.
    Writes raw PCM bytes directly to the speaker.
    """
    
    def __init__(self, sample_rate: int = 22050, channels: int = 1, sample_width: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self._pa = None
        self._stream = None
    
    def _ensure_open(self):
        """Lazy-init the PyAudio stream."""
        if self._stream is not None:
            return
        import pyaudio
        self._pa = pyaudio.PyAudio()
        fmt = {1: pyaudio.paInt8, 2: pyaudio.paInt16, 4: pyaudio.paFloat32}.get(
            self.sample_width, pyaudio.paInt16
        )
        self._stream = self._pa.open(
            format=fmt,
            channels=self.channels,
            rate=self.sample_rate,
            output=True,
        )
    
    async def play(self, pcm_bytes: bytes) -> None:
        """Play raw PCM audio bytes through speakers."""
        self._ensure_open()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._stream.write, pcm_bytes)
    
    async def play_wav(self, wav_bytes: bytes) -> None:
        """Play WAV audio (with header) through speakers."""
        import io, wave
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            # Reconfigure stream if needed
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            if sr != self.sample_rate or ch != self.channels or sw != self.sample_width:
                self.close()
                self.sample_rate = sr
                self.channels = ch
                self.sample_width = sw
            frames = wf.readframes(wf.getnframes())
        await self.play(frames)
    
    def close(self):
        """Close the audio stream."""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa:
            self._pa.terminate()
            self._pa = None


class TextToSpeech:
    """
    Text-to-Speech with universal PyAudio playback.
    Provider selected via config.audio.tts_provider or CapabilityResolver.
    """
    
    def __init__(self, voice: str = "en_US-lessac-medium", model_path: str = ""):
        from velvet.config import get_config
        self.config = get_config()
        self.voice = voice
        self.model_path = model_path
        self._voice_path: Path | None = None
        self._output = AudioOutputStream(sample_rate=22050)  # Default for Piper
        
        # Determine provider
        self._provider = self.config.audio.tts_provider
        self._impl = None
        
        if self._provider == "google":
            from velvet.services.google_ai import GoogleTextToSpeech
            self._impl = GoogleTextToSpeech()

    def load(self) -> bool:
        """Load the TTS model."""
        if self._provider == "google":
            return self._impl.load() if self._impl else False
        
        if self._provider == "pyttsx3":
            try:
                import pyttsx3
                logger.info("pyttsx3 TTS ready")
                return True
            except ImportError:
                logger.warning("pyttsx3 not installed")
                return False
        
        # Piper TTS (default)
        if self.model_path:
            model_file = Path(self.model_path)
            if not model_file.exists():
                logger.error(f"TTS model not found: {model_file}")
                return False
            self._voice_path = model_file
            self.voice = str(model_file)
            logger.info(f"Piper TTS model loaded from: {model_file}")
            return True
        
        try:
            from piper import PiperVoice
            voice_dir = Path.home() / ".local" / "share" / "piper" / "voices"
            voice_path = voice_dir / f"{self.voice}.onnx"
            
            if voice_path.exists():
                self._voice_path = voice_path
                logger.info(f"Piper voice found: {voice_path}")
                return True
            else:
                logger.warning(f"Piper voice not found: {voice_path}")
                return False
                
        except ImportError:
            logger.warning("Piper TTS not installed. Run: pip install piper-tts")
            return False
            
    async def speak(self, text: str) -> bytes | None:
        """Generate speech audio from text. Returns raw PCM or WAV bytes."""
        if not text:
            return None
            
        if self._provider == "google" and self._impl:
            return await self._impl.speak(text)
        
        if self._provider == "pyttsx3":
            try:
                import pyttsx3
                import io, wave
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                return None  # pyttsx3 plays directly, no bytes to return
            except Exception as e:
                logger.error(f"pyttsx3 TTS error: {e}")
                return None
            
        # Piper TTS
        try:
            process = await asyncio.create_subprocess_exec(
                "piper", "--model", self.voice, "--output-raw",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate(input=text.encode())
            if stdout:
                return stdout  # Raw PCM at 22050Hz
        except Exception as e:
            logger.error(f"TTS error: {e}")
            
        return None
        
    async def speak_to_device(self, text: str) -> bool:
        """Speak text directly to audio output device via universal PyAudio."""
        try:
            if self._provider == "google" and self._impl:
                audio_bytes = await self._impl.speak(text)
                if not audio_bytes:
                    return False
                # Google TTS returns WAV bytes
                await self._output.play_wav(audio_bytes)
                return True
            
            if self._provider == "pyttsx3":
                # pyttsx3 handles its own playback
                audio = await self.speak(text)
                return True
            
            # Piper: returns raw PCM at 22050Hz
            pcm = await self.speak(text)
            if pcm:
                await self._output.play(pcm)
                return True
                
        except Exception as e:
            logger.error(f"TTS playback error: {e}")
            
        return False


class AudioPipeline:
    """
    Complete audio pipeline integrating all components.
    
    Captures audio -> Wake word -> VAD -> STT -> Gateway -> TTS
    """
    
    def __init__(
        self,
        wake_word: str = "Hey Velvet",
        wake_model_path: str = "",
        whisper_model: str = "base",
        tts_voice: str = "en_US-lessac-medium",
    ):
        self.capture = AudioCapture()
        self.vad = VADProcessor()
        self.wake_detector = WakeWordDetector(
            wake_phrase=wake_word,
            model_path=wake_model_path
        )
        
        from velvet.config import get_config
        self.config = get_config()
        
        # STT provider selection via config
        if self.config.audio.stt_provider == "google":
            from velvet.services.google_ai import GoogleSpeechToText
            self.stt = GoogleSpeechToText()
            logger.info("Using Google STT (via config)")
        else:
            self.stt = SpeechToText(model_size=whisper_model)
            logger.info("Using Whisper STT (via config)")
            
        self.tts = TextToSpeech(voice=tts_voice)
        
        self._running = False
        self._is_awake = False
        self._task: asyncio.Task | None = None
        
    async def start(self) -> None:
        """Start the audio pipeline."""
        logger.info("Starting audio pipeline...")
        
        # Load models
        self.vad.load()
        self.wake_detector.load()
        self.stt.load()
        self.tts.load()
        
        # Start capture
        await self.capture.start()
        
        # Start processing task
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        
        logger.info("Audio pipeline started")
        
    async def stop(self) -> None:
        """Stop the audio pipeline."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
        await self.capture.stop()
        logger.info("Audio pipeline stopped")
        
    async def _process_loop(self) -> None:
        """Main audio processing loop."""
        fabric = get_fabric()
        
        while self._running:
            try:
                # Get audio chunk
                chunk = await self.capture.get_chunk(timeout=0.5)
                if not chunk:
                    continue
                    
                # Check for wake word if not already awake
                if not self._is_awake:
                    detected, confidence = self.wake_detector.process_chunk(chunk)
                    if detected:
                        self._is_awake = True
                        await fabric.publish(
                            MessageType.WAKE_WORD.value,
                            {"phrase": self.wake_detector.wake_phrase, "confidence": float(confidence)}
                        )
                        logger.info("[MIC] Listening...")
                        continue
                        
                # If awake, process for speech
                if self._is_awake:
                    is_speech, completed_audio = self.vad.process_chunk(chunk)
                    
                    if completed_audio:
                        # Speech segment complete, transcribe it
                        logger.info("📝 Transcribing...")
                        text = await self.stt.transcribe(completed_audio)
                        
                        if text.strip():
                            logger.info(f"💬 You said: {text}")
                            await fabric.publish(
                                MessageType.TRANSCRIPT.value,
                                {"text": text, "is_final": True}
                            )
                            
                        # Reset to waiting for wake word
                        self._is_awake = False
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audio pipeline error: {e}")
                await asyncio.sleep(0.1)
                
    async def force_wake(self) -> None:
        """Force the system into awake/listening mode."""
        self._is_awake = True
        fabric = get_fabric()
        await fabric.publish(
            MessageType.WAKE_WORD.value,
            {"phrase": "manual", "confidence": 1.0}
        )
