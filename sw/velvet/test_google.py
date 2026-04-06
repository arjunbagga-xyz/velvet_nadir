import asyncio
import os
import io
import time
from loguru import logger

async def test_llm():
    try:
        from google import genai
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents='Hello, world!'
        )
        print("LLM RESPONSE:", response.text)
    except Exception as e:
        print("LLM ERROR:", e)

async def test_stt():
    try:
        from google import genai
        from google.genai import types
        client = genai.Client()
        
        # Create a dummy silent wav
        import wave
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b'\x00' * 16000 * 2)  # 1s silence
            audio_bytes = wav_io.getvalue()
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type='audio/wav'),
                "Transcribe this audio. If silent, say 'SILENCE'."
            ]
        )
        print("STT RESPONSE:", response.text)
    except Exception as e:
        print("STT ERROR:", e)

async def test_tts():
    try:
        # Check if gemini supports speech output via google.genai
        from google import genai
        from google.genai import types
        client = genai.Client()
        
        # Current google-genai supports audio out on gemini-2.0-flash-exp, but let's see.
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents='Say hello world',
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"]
                )
            )
            print("TTS RESPONSE keys:", type(response))
        except Exception as e:
            print("Gemini TTS Error:", e)
            print("Falling back to gTTS test.")
            from gtts import gTTS
            tts = gTTS(text="Hello world", lang='en')
            tts.save("test_tts.mp3")
            print("gTTS success.")

    except Exception as e:
        print("TTS ERROR:", e)

if __name__ == "__main__":
    asyncio.run(test_llm())
    asyncio.run(test_stt())
    asyncio.run(test_tts())
