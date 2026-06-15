from __future__ import annotations

import os
import asyncio
from typing import AsyncIterator, Any
from loguru import logger
import aiohttp

from velvet.llm import LLMAdapter, LLMResponse, LLMAdapterError

class UniversalCloudLLMAdapter(LLMAdapter):
    """
    Universal Cloud LLM Adapter.
    Delegates to GoogleAIAdapter for Gemini, and uses standard OpenAI-compatible
    HTTP completions API for NVIDIA NIM and OpenRouter.
    """
    
    def __init__(self, provider: str = "google", model: str = None, api_key: str = None, **kwargs):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.kwargs = kwargs
        self._session = None
        self._delegate = None
        
        # Check security gate at init time
        from velvet.config import get_config
        cfg = get_config()
        allow_cloud = getattr(cfg.security, 'allow_cloud_adapters', False) or getattr(cfg.security, 'allow_google_adapter', False)
        if not allow_cloud:
            raise LLMAdapterError(
                f"Cloud adapter for provider '{self.provider}' blocked by security policy. "
                "Set VELVET_SECURITY_ALLOW_CLOUD_ADAPTERS=true in velvet.toml to opt in."
            )
            
        if self.provider == "google":
            from velvet.services.google_ai import GoogleAIAdapter
            # Fallback model for Google
            self.model = self.model or "gemini-2.5-flash"
            self._delegate = GoogleAIAdapter(model=self.model, api_key=self.api_key, **kwargs)
        elif self.provider == "nvidia":
            self.model = self.model or "nvidia/llama-3.3-nemotron-super-49b-v1"
            self.api_key = self.api_key or os.environ.get("VELVET_LLM_NVIDIA_API_KEY")
            self.base_url = "https://integrate.api.nvidia.com/v1"
            if not self.api_key:
                raise LLMAdapterError("NVIDIA API key missing (VELVET_LLM_NVIDIA_API_KEY).")
        elif self.provider == "openrouter":
            self.model = self.model or "google/gemini-2.5-flash"
            self.api_key = self.api_key or os.environ.get("VELVET_LLM_OPENROUTER_API_KEY")
            self.base_url = "https://openrouter.ai/api/v1"
            if not self.api_key:
                raise LLMAdapterError("OpenRouter API key missing (VELVET_LLM_OPENROUTER_API_KEY).")
        else:
            raise LLMAdapterError(f"Unsupported cloud provider: {provider}")

    async def _ensure_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
        if self._delegate and hasattr(self._delegate, "close"):
            await self._delegate.close()

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        images: list[str] = None
    ) -> LLMResponse:
        
        # PrivacyGuard & Mirage Protocol Enforcement
        try:
            from velvet.privacy import PrivacyClassifier, PrivacyLevel, PrivacyViolation
            classifier = PrivacyClassifier()
            max_level = PrivacyLevel.PUBLIC
            for m in messages:
                content = m.get("content", "")
                if isinstance(content, str):
                    level = classifier.classify(content)
                    if level > max_level:
                        max_level = level
                        
            if max_level == PrivacyLevel.RESTRICTED:
                raise PrivacyViolation("RESTRICTED data cannot be sent to cloud")
                
            smap = None
            scrambled_messages = messages
            proxy = None
            
            if max_level >= PrivacyLevel.PERSONAL:
                from velvet.mirage import MirageProxy, MirageMap
                proxy = MirageProxy()
                scrambled_messages = []
                smap = MirageMap()
                for m in messages:
                    content = m.get("content", "")
                    if isinstance(content, str) and content:
                        scrambled_text, smap = proxy.scramble(content, smap)
                        scrambled_messages.append({**m, "content": scrambled_text})
                    else:
                        scrambled_messages.append(m)
        except PrivacyViolation:
            raise
        except Exception as e:
            logger.debug(f"PrivacyGuard classification/scramble error: {e}")
            scrambled_messages = messages
            smap = None
            proxy = None

        # Delegate to GoogleAIAdapter if provider is google
        if self._delegate:
            response = await self._delegate.generate(
                scrambled_messages, tools=tools, max_tokens=max_tokens, temperature=temperature, images=images
            )
            if proxy and smap and response.text:
                response.text = proxy.rehydrate(response.text, smap)
            return response
            
        await self._ensure_session()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/arjunbagga-xyz/velvet_nadir"
            headers["X-Title"] = "Velvet Nadir"
            
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": scrambled_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            
        try:
            async with self._session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"[UniversalLLM] API error ({self.provider}): {error_text}")
                    return LLMResponse(text=f"Error: {error_text}", finish_reason="error")
                    
                data = await resp.json()
                choice = data["choices"][0]
                message = choice["message"]
                
                tool_calls = None
                raw_calls = message.get("tool_calls")
                if raw_calls:
                    tool_calls = []
                    for rc in raw_calls:
                        func = rc.get("function", {})
                        import json
                        args = func.get("arguments", "{}")
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                pass
                        tool_calls.append({
                            "tool": func.get("name"),
                            "params": args
                        })
                        
                text = message.get("content") or ""
                if proxy and smap and text:
                    text = proxy.rehydrate(text, smap)
                    
                finish_reason = choice.get("finish_reason", "stop")
                if tool_calls:
                    finish_reason = "tool_calls"
                    
                return LLMResponse(
                    text=text,
                    tool_calls=tool_calls,
                    finish_reason=finish_reason,
                    tokens_used=data.get("usage", {}).get("total_tokens", 0)
                )
        except Exception as e:
            logger.error(f"[UniversalLLM] Failed request: {e}")
            return LLMResponse(text=f"Error: {e}", finish_reason="error")

    async def stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        # Run classification for streaming delegate
        try:
            from velvet.privacy import PrivacyClassifier, PrivacyLevel, PrivacyViolation
            classifier = PrivacyClassifier()
            max_level = PrivacyLevel.PUBLIC
            for m in messages:
                content = m.get("content", "")
                if isinstance(content, str):
                    level = classifier.classify(content)
                    if level > max_level:
                        max_level = level
                        
            if max_level == PrivacyLevel.RESTRICTED:
                raise PrivacyViolation("RESTRICTED data cannot be sent to cloud")
                
            smap = None
            scrambled_messages = messages
            proxy = None
            
            if max_level >= PrivacyLevel.PERSONAL:
                from velvet.mirage import MirageProxy, MirageMap
                proxy = MirageProxy()
                scrambled_messages = []
                smap = MirageMap()
                for m in messages:
                    content = m.get("content", "")
                    if isinstance(content, str) and content:
                        scrambled_text, smap = proxy.scramble(content, smap)
                        scrambled_messages.append({**m, "content": scrambled_text})
                    else:
                        scrambled_messages.append(m)
        except PrivacyViolation:
            raise
        except Exception as e:
            logger.debug(f"PrivacyGuard classification/scramble stream error: {e}")
            scrambled_messages = messages
            smap = None
            proxy = None

        if self._delegate:
            async for chunk in self._delegate.stream(scrambled_messages, max_tokens, temperature):
                yield proxy.rehydrate(chunk, smap) if (proxy and smap) else chunk
            return
            
        # Fallback to standard generate for NVIDIA/OpenRouter stream
        # self.generate will do its own classification, scrambling, and rehydration.
        response = await self.generate(messages, max_tokens=max_tokens, temperature=temperature)
        yield response.text
