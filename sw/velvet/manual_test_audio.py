"""
Audio pipeline integration test.

Tests:
1. PyAudio - microphone device detection
2. OpenWakeWord - model loading (ONNX runtime)
3. Faster-Whisper - model download + transcription
4. End-to-end mic capture (2 second recording)
"""

import sys
import time
import numpy as np

print("=" * 60)
print("  VELVET NADIR — Audio Pipeline Test")
print("=" * 60)

# ── 1. PyAudio ──
print("\n1. PyAudio — checking microphone...")
try:
    import pyaudio
    pa = pyaudio.PyAudio()
    count = pa.get_device_count()
    print(f"   Devices found: {count}")
    
    try:
        info = pa.get_default_input_device_info()
        print(f"   Default input: {info['name']}")
        print(f"   Sample rate: {int(info['defaultSampleRate'])} Hz")
        print(f"   Max channels: {info['maxInputChannels']}")
        print("   [OK] PyAudio")
    except IOError:
        print("   [FAIL] No default input device found!")
        pa.terminate()
        sys.exit(1)
    
    pa.terminate()
except Exception as e:
    print(f"   [FAIL] {e}")
    sys.exit(1)

# ── 2. OpenWakeWord ──
print("\n2. OpenWakeWord — loading model (ONNX)...")
try:
    from openwakeword.model import Model
    
    # Use inference_framework="onnx" for Windows (no tflite wheels)
    model = Model(
        wakeword_models=["hey_jarvis"],
        inference_framework="onnx",
    )
    print(f"   Models loaded: {list(model.prediction_buffer.keys())}")
    
    # Test with silence
    silence = np.zeros(1280, dtype=np.int16)
    predictions = model.predict(silence)
    print(f"   Predictions on silence: {predictions}")
    print("   [OK] OpenWakeWord")
except Exception as e:
    print(f"   [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ── 3. Faster-Whisper ──
print("\n3. Faster-Whisper — downloading 'tiny' model...")
try:
    from faster_whisper import WhisperModel
    
    t0 = time.time()
    # 'tiny' is ~39MB, smallest available
    whisper = WhisperModel("tiny", device="cpu", compute_type="int8")
    dt = time.time() - t0
    print(f"   Model loaded in {dt:.1f}s")
    
    # Test with 1 second of silence
    silence_audio = np.zeros(16000, dtype=np.float32)
    segments, info = whisper.transcribe(silence_audio, beam_size=1)
    text = " ".join(s.text for s in segments)
    print(f"   Detected language: {info.language} ({info.language_probability:.2f})")
    print(f"   Transcription of silence: '{text.strip()}'")
    print("   [OK] Faster-Whisper")
except Exception as e:
    print(f"   [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ── 4. Mic Capture Test ──
print("\n4. Mic capture — recording 2 seconds...")
try:
    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=16000,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=1280,
    )
    
    chunks = []
    num_chunks = int(16000 * 2 / 1280)  # 2 seconds = 25 chunks
    
    for i in range(num_chunks):
        data = stream.read(1280, exception_on_overflow=False)
        chunks.append(data)
    
    stream.close()
    pa.terminate()
    
    # Analyze
    all_audio = b"".join(chunks)
    audio_array = np.frombuffer(all_audio, dtype=np.int16)
    energy = float(np.abs(audio_array).mean())
    peak = float(np.abs(audio_array).max())
    
    print(f"   Captured: {len(all_audio)} bytes ({len(chunks)} chunks)")
    print(f"   Mean energy: {energy:.0f}")
    print(f"   Peak: {peak:.0f}")
    
    # Transcribe the recording
    audio_float = audio_array.astype(np.float32) / 32768.0
    segments, info = whisper.transcribe(audio_float, beam_size=1)
    text = " ".join(s.text for s in segments)
    print(f"   Transcription: '{text.strip()}'")
    print("   [OK] Mic capture")
    
except Exception as e:
    print(f"   [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ── 5. Wake word + mic combined ──
print("\n5. Wake word detection on mic audio (2 seconds)...")
try:
    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=16000,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=1280,
    )
    
    wake_count = 0
    num_chunks = int(16000 * 2 / 1280)
    
    for i in range(num_chunks):
        data = stream.read(1280, exception_on_overflow=False)
        audio_array = np.frombuffer(data, dtype=np.int16)
        predictions = model.predict(audio_array)
        for name, score in predictions.items():
            if score > 0.5:
                wake_count += 1
                print(f"   Wake detected: {name} ({score:.2f})")
    
    stream.close()
    pa.terminate()
    
    if wake_count == 0:
        print("   No wake word detected (expected - nobody said it)")
    print("   [OK] Wake word + mic combined")
    
except Exception as e:
    print(f"   [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ── Summary ──
print("\n" + "=" * 60)
print("  ✅ All audio pipeline tests passed!")
print("=" * 60)
print("\nReady for real audio mode:")
print("  set VELVET_AUDIO_USE_REAL_AUDIO=true")
print("  python -m velvet console")
