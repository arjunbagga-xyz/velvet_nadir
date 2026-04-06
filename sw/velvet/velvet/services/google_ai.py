"""
Google AI Pipeline Adapters.

Wraps Google Gemini (for LLM, Vision, STT) and gTTS (for TTS) into Velvet's
class structures so we can run a "Real" pipeline without heavy local models.
"""

import os
import io
import asyncio
from typing import AsyncIterator, Any
from loguru import logger

from velvet.config import get_config
from velvet.llm import LLMAdapter, LLMResponse

class GoogleAIAdapter(LLMAdapter):
    """
    Adapter for Google Gemini APIs using the `google-genai` SDK.
    Handles Text, Vision (via base64 images), and function calling.
    """
    def __init__(self, model: str = "gemini-3-flash-preview", api_key: str = None, **kwargs):
        self.model = model
        self.api_key = api_key or os.environ.get("VELVET_LLM_GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key missing.")
            
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except ImportError:
            raise ImportError("Please install google-genai: pip install google-genai")

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        images: list[str] = None
    ) -> LLMResponse:
        """Call Gemini via google-genai SDK."""
        from google.genai import types
        import base64
        
        # Convert internal format to Gemini payload format
        contents = []
        
        # Parse system prompt from messages
        system_instruction = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                # We can only have one system instruction in Gemini config
                if system_instruction:
                    system_instruction += "\n\n" + msg["content"]
                else:
                    system_instruction = msg["content"]
            else:
                user_messages.append(msg)
        
        # We will bundle the user history
        # For a simple adapter, let's just make the last message multimodal
        history_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in user_messages])
        
        parts = []
        if images:
            for img_b64 in images:
                img_bytes = base64.b64decode(img_b64)
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'))
        
        parts.append(history_text)
        
        # Tools
        gemini_tools = None
        if tools:
            # We must convert Velvet's OpenAI-like tool format to Gemini format
            gemini_tools = [self._convert_tool(t) for t in tools if t.get("type") == "function"]

        config_kwargs = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
            
        if gemini_tools:
            config_kwargs["tools"] = gemini_tools

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=self.model,
                    contents=parts,
                    config=types.GenerateContentConfig(**config_kwargs)
                )
            )
            
            # Extract tool calls
            tool_calls = None
            text = response.text or ""
            if response.function_calls:
                tool_calls = []
                for fc in response.function_calls:
                    # google-genai function calls: fc.name, fc.args (dict)
                    tool_calls.append({
                        "tool": fc.name,
                        "params": fc.args
                    })
                    
            finish_reason = "tool_calls" if tool_calls else "stop"
            return LLMResponse(text=text, tool_calls=tool_calls, finish_reason=finish_reason)
            
        except Exception as e:
            logger.error(f"GoogleAI error: {e}")
            return LLMResponse(text=f"Error: {e}", finish_reason="error")

    async def stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream tokens from Gemini. For now, falls back to standard generate."""
        response = await self.generate(messages, max_tokens=max_tokens, temperature=temperature)
        yield response.text

    def _convert_tool(self, tool: dict) -> Any:
        from google.genai import types
        func = tool.get("function", {})
        params = func.get("parameters", {})
        
        # Build proper Gemini parameter schema from JSON Schema
        properties = {}
        for prop_name, prop_schema in params.get("properties", {}).items():
            prop_type = prop_schema.get("type", "STRING").upper()
            # Map JSON Schema types to Gemini types
            type_map = {"STRING": "STRING", "INTEGER": "INTEGER", "NUMBER": "NUMBER", 
                       "BOOLEAN": "BOOLEAN", "ARRAY": "ARRAY", "OBJECT": "OBJECT"}
            properties[prop_name] = types.Schema(
                type=type_map.get(prop_type, "STRING"),
                description=prop_schema.get("description", ""),
            )
        
        schema = None
        if properties:
            schema = types.Schema(
                type="OBJECT",
                properties=properties,
                required=params.get("required", []),
            )
        
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=func.get("name"),
                    description=func.get("description"),
                    parameters=schema,
                )
            ]
        )

# ====== AUDIO ======

class GoogleSpeechToText:
    """Uses Gemini 1.5 Flash to transcribe audio files via Audio modality."""
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("VELVET_LLM_GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key missing.")
        from google import genai
        self.client = genai.Client(api_key=self.api_key)
        self.model = 'gemini-3-flash-preview'
        
    def load(self): return True
    
    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if len(audio_data) < 4000: # Too short
            return ""
            
        from google.genai import types
        import wave
        import io
        
        # Wrap raw PCM to WAV
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(audio_data)
            wav_bytes = wav_io.getvalue()
            
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_bytes(data=wav_bytes, mime_type='audio/wav'),
                        "Transcribe the audio accurately. Only return the transcription text. If silence, return NOTHING."
                    ]
                )
            )
            text = response.text.strip()
            if "NOTHING" in text or "SILENCE" in text:
                return ""
            print(f"[STT] Transcribed: {text}")
            return text
        except Exception as e:
            logger.error(f"Google STT Error: {e}")
            return ""

class GoogleTextToSpeech:
    """Uses pyttsx3 for fast native TTS on Windows to avoid ffmpeg requirements."""
    def __init__(self):
        self.lang = 'en'
        
    def load(self):
        try:
            import pyttsx3
            return True
        except ImportError:
            logger.error("Please install pyttsx3: pip install pyttsx3")
            return False
            
    async def speak(self, text: str) -> bytes | None:
        if not text: return None
        try:
            import pyttsx3
            import asyncio
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                
            def generate_wav():
                engine = pyttsx3.init()
                engine.save_to_file(text, temp_path)
                engine.runAndWait()
                
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, generate_wav)
            
            with open(temp_path, "rb") as f:
                wav_data = f.read()
            os.unlink(temp_path)
            
            return wav_data
            
        except Exception as e:
            logger.error(f"TTS Error: {e}")
            return None
