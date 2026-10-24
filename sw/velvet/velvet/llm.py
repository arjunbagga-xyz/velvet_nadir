"""
LLM integration for Velvet Nadir.

Provides adapters for:
- llama.cpp (via llama-cpp-python)
- Ollama (via HTTP API)

Both support streaming and function calling.
"""

__all__ = [
    "LLMResponse",
    "LLMAdapter",
    "LLMAdapterError",
    "OllamaAdapter",
    "LlamaCppAdapter",
    "VLLMAdapter",
    "MeshLLMAdapter",
    "NodeCooldown",
    "create_llm_adapter",
    "get_llm_adapter",
    "VELVET_SYSTEM_PROMPT",
]

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from loguru import logger

from velvet.errors import LLMAdapterError
from velvet.reliability import (
    repair_truncated_tool_call,
    coerce_tool_arguments,
    check_empty_response,
    strip_think_blocks,
    EmptyResponseError,
)


@dataclass
class NodeCooldown:
    """Tracks failure counts and exponential backoff for a mesh node."""
    device_id: str
    failure_count: int = 0
    until: float = 0.0
    last_error: str = ""

    def is_active(self) -> bool:
        return time.time() < self.until

    def backoff(self, error: str = "") -> None:
        backoffs = [60.0, 120.0, 300.0, 900.0, 3600.0]
        idx = min(self.failure_count, len(backoffs) - 1)
        delay = backoffs[idx]
        self.failure_count += 1
        self.until = time.time() + delay
        self.last_error = error

    def reset(self) -> None:
        self.failure_count = 0
        self.until = 0.0
        self.last_error = ""


@dataclass
class LLMResponse:
    """Response from an LLM."""
    text: str
    tool_calls: list[dict] | None = None
    finish_reason: str = "stop"
    tokens_used: int = 0


class LLMAdapter(ABC):
    """Base class for LLM adapters."""
    
    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        pass
        
    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream tokens from the LLM."""
        pass


class OllamaAdapter(LLMAdapter):
    """
    Adapter for Ollama API.
    
    Ollama is the easiest way to run LLMs locally.
    Install from: https://ollama.ai
    """
    
    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url
        self._session = None
        
    async def _ensure_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
            
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
            
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        images: list[str] | None = None,
    ) -> LLMResponse:
        """Generate a response using Ollama."""
        await self._ensure_session()
        
        # In Ollama /api/chat, images are per message or global.
        # We allow passing them as a separate list or attached to messages.
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
            "stream": False,
        }
        
        # If images provided, attach to last message
        if images and len(messages) > 0:
            last_msg = messages[-1].copy()
            last_msg["images"] = images
            # Replace last message with one containing images
            payload["messages"][-1] = last_msg

        # Add tools if provided (Ollama supports function calling)
        if tools:
            payload["tools"] = tools
            
        try:
            async with self._session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Ollama Error {resp.status}: {text}")
                    return LLMResponse(text=f"Error: {text}")
                    
                data = await resp.json()
                message = data.get("message", {})
                
                # Check for tool calls
                raw_tool_calls = message.get("tool_calls")
                tool_calls = None
                if raw_tool_calls:
                    tool_calls = []
                    for tc in raw_tool_calls:
                        func = tc.get("function", {})
                        args = func.get("arguments", {})
                        if isinstance(args, str):
                            args = repair_truncated_tool_call(args)
                        func["arguments"] = args
                        tool_calls.append(tc)
                
                raw_content = message.get("content", "") or ""
                clean_content = strip_think_blocks(raw_content)

                if check_empty_response(clean_content, tool_calls):
                    return LLMResponse(
                        text="Error: Empty response from model",
                        finish_reason="error",
                    )
                
                return LLMResponse(
                    text=clean_content,
                    tool_calls=tool_calls,
                    finish_reason="tool_calls" if tool_calls else "stop",
                    tokens_used=data.get("eval_count", 0),
                )
                
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return LLMResponse(text=f"Error connecting to LLM: {e}", finish_reason="error")
            
    async def stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream tokens from Ollama."""
        await self._ensure_session()
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        
        try:
            async with self._session.post(f"{self.base_url}/api/chat", json=payload) as resp:
                if resp.status != 200:
                    yield f"Error: {await resp.text()}"
                    return

                async for line in resp.content:
                    if not line: continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except:
                        pass
                            
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Ollama stream failed: {e}")
            yield f"Error: {e}"


class MeshLLMAdapter(LLMAdapter):
    """
    Smart Mesh Router for LLM requests.
    
    Instead of running inference directly, it:
    1. Consults HardwareRegistry for available 'llm' providers.
    2. Scores them based on Load (active_tasks) and Locality.
    3. Routes the request:
       - If Local is best -> Call local LLMService (Direct).
       - If Remote is best -> Publish to Fabric and await response.
    """
    
    def __init__(self, service_provider=None, affinity_tracker=None):
        # Assuming get_fabric and get_config are available globally or imported
        from velvet.fabric import get_fabric
        from velvet.config import get_config
        self.fabric = get_fabric()
        self.config = get_config()
        self.local_id = self.config.zenoh.device_id
        # Optional: Direct reference to local service if running in same process
        self.local_service = service_provider 
        self._affinity_tracker = affinity_tracker
        self._node_cooldowns: dict[str, NodeCooldown] = {}
        
    @property
    def affinity_tracker(self):
        if self._affinity_tracker is None:
            try:
                from velvet.gateway import get_gateway
                gw = get_gateway()
                self._affinity_tracker = gw._affinity_tracker
            except Exception:
                pass
        return self._affinity_tracker
        
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        images: list[str] = None
    ) -> LLMResponse:
        
        # 1. Identify task type
        task_type = "chat"
        if tools:
            task_type = "tool_call"
        elif any("code" in m.get("content", "").lower() for m in messages if m.get("role") == "system"):
            task_type = "code_gen"

        # 2. Retry loop with node cooldowns
        max_retries = 3
        attempted_nodes: set[str] = set()
        last_error = "No capable LLM nodes found on the mesh."

        for attempt in range(max_retries):
            best_node = self._select_best_node(task_type, exclude_device_ids=attempted_nodes)
            if not best_node:
                break
            attempted_nodes.add(best_node.device_id)

            try:
                if best_node.device_id == self.local_id and self.local_service:
                    logger.info(f"[MeshLLM] Routing locally (Fast Path, attempt {attempt + 1})")
                    resp = await self.local_service.backend.generate(
                        messages, tools=tools, max_tokens=max_tokens, temperature=temperature, images=images
                    )
                else:
                    logger.info(
                        f"[MeshLLM] Routing to remote node: {best_node.device_id} "
                        f"(Tasks: {best_node.load.active_tasks}, attempt {attempt + 1})"
                    )
                    resp = await self._remote_request(best_node.device_id, messages, tools, images)

                if resp.finish_reason == "error" or (resp.text and resp.text.startswith("Error:")):
                    err_msg = resp.text
                    if best_node.device_id not in self._node_cooldowns:
                        self._node_cooldowns[best_node.device_id] = NodeCooldown(best_node.device_id)
                    self._node_cooldowns[best_node.device_id].backoff(err_msg)
                    last_error = err_msg
                    continue

                # Successful execution resets cooldown
                if best_node.device_id in self._node_cooldowns:
                    self._node_cooldowns[best_node.device_id].reset()
                return resp

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[MeshLLM] Execution failed on {best_node.device_id}: {e}")
                try:
                    from velvet.reliability.error_classifier import ErrorClassifier
                    classified = ErrorClassifier.classify(e)
                    last_error = f"[{classified.category.value}] {classified.user_message}: {e}"
                except Exception:
                    last_error = str(e)

                if best_node.device_id not in self._node_cooldowns:
                    self._node_cooldowns[best_node.device_id] = NodeCooldown(best_node.device_id)
                self._node_cooldowns[best_node.device_id].backoff(str(e))
                continue

        return LLMResponse(
            text=f"Error: All {len(attempted_nodes)} mesh LLM attempts failed. Last error: {last_error}",
            finish_reason="error",
        )

    async def generate_judge(
        self,
        messages: list[dict],
        criteria: str,
        exclude_device_id: str | None = None,
        exclude_model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """
        Route evaluation to an independent node/model on the mesh.
        Strictly avoids self-grading by excluding the generator's device and/or model.
        """
        judge_messages = [
            {"role": "system", "content": f"You are an impartial evaluator. Judge against criteria: {criteria}"},
            *messages,
        ]
        best_node = self._select_best_node(
            task_type="judge",
            exclude_device_id=exclude_device_id,
            exclude_model=exclude_model,
        )
        if not best_node:
            # Fallback to any node
            best_node = self._select_best_node(task_type="judge")
        if not best_node:
            return LLMResponse("Error: No capable judge node found on mesh.", finish_reason="error")

        try:
            if best_node.device_id == self.local_id and self.local_service:
                return await self.local_service.backend.generate(
                    judge_messages, max_tokens=max_tokens, temperature=temperature
                )
            else:
                return await self._remote_request(best_node.device_id, judge_messages, tools=None, images=None)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return LLMResponse(f"Error: Judge evaluation failed: {e}", finish_reason="error")

    async def stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream tokens from the LLM."""
        # For streaming, we'd need a different remote request mechanism
        # that yields chunks. For MVP, we might just generate and return
        # the full text, or implement a separate streaming remote path.
        # For now, let's just call generate and yield the result as a single chunk.
        logger.warning("[MeshLLM] Stream method currently uses generate for remote calls.")
        response = await self.generate(messages, max_tokens=max_tokens, temperature=temperature)
        if response.text:
            yield response.text
        if response.finish_reason == "error":
            logger.error(f"[MeshLLM] Stream error: {response.text}")


    def _select_best_node(
        self,
        task_type: str = "chat",
        exclude_device_id: str | None = None,
        exclude_model: str | None = None,
        exclude_device_ids: set[str] | None = None,
    ):
        """Find the best node based on Load, Locality, Model Affinity, and Cooldowns."""
        from velvet.devices import get_registry
        try:
            registry = get_registry()
            candidates = registry.get_online_devices()
            logger.info(f"[MeshLLM] Found {len(candidates)} online devices: {[d.device_id for d in candidates]}")
            
            # Find the best model for this task type
            best_model = None
            if self.affinity_tracker:
                best_model = self.affinity_tracker.best_model_for(task_type)
                if best_model:
                    logger.debug(f"[MeshLLM] Best model from affinity tracker for '{task_type}': {best_model}")
            
            scored = []
            for d in candidates:
                logger.info(f"[MeshLLM] Checking candidate {d.device_id} - status: {d.status}, type: {d.device_type}")
                
                # Check exclusions
                if exclude_device_id and d.device_id == exclude_device_id:
                    continue
                if exclude_device_ids and d.device_id in exclude_device_ids:
                    continue
                if exclude_model and hasattr(d, 'loaded_models') and d.loaded_models:
                    if any(exclude_model in m for m in d.loaded_models):
                        continue

                score = 50 # Base score for remote
                
                # Locality Bonus
                if d.device_id == self.local_id:
                    score = 100
                
                # Load Penalty (-10 per active task)
                score -= (d.load.active_tasks * 10)
                
                # Model Affinity Bonus
                if best_model and hasattr(d, 'loaded_models') and d.loaded_models:
                    if any(best_model in m for m in d.loaded_models):
                        logger.info(f"[MeshLLM] Node {d.device_id} gets affinity bonus for model {best_model}")
                        score += 30
                
                # Active Cooldown Penalty
                cd = self._node_cooldowns.get(d.device_id)
                if cd and cd.is_active():
                    score -= 1000
                
                scored.append((score, d))
            
            if not scored:
                return None
                
            # Sort descending
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]
            
        except Exception as e:
            logger.error(f"[MeshLLM] Selection failed: {e}")
            return None

    async def _remote_request(self, target_id: str, messages: list, tools: list, images: list) -> LLMResponse:
        import uuid
        import time
        request_id = str(uuid.uuid4())
        reply_topic = f"velvet/mesh/llm/response/{request_id}"
        
        payload = {
            "request_id": request_id,
            "reply_to": reply_topic,
            "messages": messages,
            "tools": tools,
            "images": images
        }
        
        # Subscribe to response
        future = asyncio.Future()
        
        async def on_response(msg):
            future.set_result(msg.payload)  # Already a dict via VelvetMessage
            
        await self.fabric.subscribe(reply_topic, on_response)
        
        try:
            # Send Request (pass dict — publish() wraps in VelvetMessage + msgpack)
            topic = f"velvet/mesh/llm/request/{target_id}"
            await self.fabric.publish(topic, payload)
            
            # Wait (Timeout 30s)
            start_t = time.perf_counter()
            data = await asyncio.wait_for(future, timeout=30.0)
            
            if "error" in data:
                 return LLMResponse(f"Remote Error: {data['error']}", finish_reason="error")
                 
            return LLMResponse(
                text=data.get("text", ""),
                tool_calls=data.get("tool_calls"),
                tokens_used=data.get("tokens_used", 0)
            )
            
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            return LLMResponse("Error: Remote LLM timed out.", finish_reason="error")
        except Exception as e:
            return LLMResponse(f"Error: {e}", finish_reason="error")
        finally:
            # Clean up subscription via unsubscribe (not sub.undeclare)
            await self.fabric.unsubscribe(reply_topic, on_response)


class LlamaCppAdapter(LLMAdapter):
    """
    Adapter for llama.cpp via llama-cpp-python.
    
    Runs LLMs directly without a server.
    Install: pip install llama-cpp-python
    """
    
    def __init__(
        self,
        model_path: str,
        n_ctx: int = 8192,
        n_gpu_layers: int = -1,  # -1 = use all GPU layers
    ):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self._model = None
        
    def load(self) -> bool:
        """Load the model."""
        try:
            from llama_cpp import Llama
            
            logger.info(f"Loading model: {self.model_path}")
            self._model = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                chat_format="llama-3",  # Adjust based on model
            )
            logger.info("Model loaded")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
            
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response using llama.cpp."""
        if not self._model:
            return LLMResponse(text="Model not loaded", finish_reason="error")
            
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            
            # Add tool descriptions to system message if tools provided
            if tools:
                tool_desc = self._format_tools_for_prompt(tools)
                messages = self._inject_tools_prompt(messages, tool_desc)
                
            response = await loop.run_in_executor(
                None,
                lambda: self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            )
            
            content = response["choices"][0]["message"]["content"]
            
            # Try to parse tool calls from content
            tool_calls = self._extract_tool_calls(content) if tools else None
            
            return LLMResponse(
                text=content if not tool_calls else "",
                tool_calls=tool_calls,
                finish_reason="tool_calls" if tool_calls else "stop",
                tokens_used=response.get("usage", {}).get("total_tokens", 0),
            )
            
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"llama.cpp generation failed: {e}")
            return LLMResponse(text=f"Error: {e}", finish_reason="error")
            
    async def stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream tokens from llama.cpp."""
        if not self._model:
            yield "Model not loaded"
            return
            
        try:
            loop = asyncio.get_running_loop()
            
            # Create streaming generator
            def _stream():
                return self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                )
                
            stream_gen = await loop.run_in_executor(None, _stream)
            
            for chunk in stream_gen:
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta:
                    yield delta["content"]
                    
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"llama.cpp stream failed: {e}")
            yield f"Error: {e}"
            
    def _format_tools_for_prompt(self, tools: list[dict]) -> str:
        """Format tools as text for the prompt."""
        lines = ["Available functions:"]
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                params = func.get("parameters", {}).get("properties", {})
                param_str = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in params.items())
                lines.append(f"- {func['name']}({param_str}): {func['description']}")
        return "\n".join(lines)
        
    def _inject_tools_prompt(self, messages: list[dict], tool_desc: str) -> list[dict]:
        """Inject tool descriptions into the system prompt."""
        tool_instruction = f"""
{tool_desc}

To call a function, respond with JSON in this format:
{{"function": "function_name", "arguments": {{"arg1": "value1"}}}}

Only use JSON format if you want to call a function. Otherwise respond normally.
"""
        
        # Add to system message or create one
        if messages and messages[0].get("role") == "system":
            messages = messages.copy()
            messages[0] = {
                "role": "system",
                "content": messages[0]["content"] + "\n\n" + tool_instruction,
            }
        else:
            messages = [{"role": "system", "content": tool_instruction}] + messages
            
        return messages
        
    def _extract_tool_calls(self, content: str) -> list[dict] | None:
        """Try to extract tool calls from the response, with automatic truncated JSON repair."""
        try:
            # Look for JSON in the response
            import re
            json_match = re.search(r'\{[^{}]*"function"[^{}]*\}', content)
            if json_match:
                call = repair_truncated_tool_call(json_match.group())
                if isinstance(call, dict) and "function" in call:
                    args = call.get("arguments", {})
                    return [{
                        "function": {
                            "name": call["function"],
                            "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                        }
                    }]
        except Exception:
            pass
        return None


class VLLMAdapter(LLMAdapter):
    """
    Adapter for vLLM's OpenAI-compatible API.

    vLLM provides high-throughput inference with PagedAttention.
    Start with: python -m vllm.entrypoints.openai.api_server --model <model>
    
    Uses aiohttp to hit /v1/chat/completions — same protocol as OpenAI,
    so this also works with any OpenAI-compatible server.
    """

    def __init__(
        self,
        model: str = "meta-llama/Llama-3.1-8B-Instruct",
        base_url: str = "http://localhost:8000",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._session = None

    async def _ensure_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response using vLLM's OpenAI-compatible API."""
        await self._ensure_session()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            async with self._session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"vLLM error: {error}")
                    return LLMResponse(text=f"Error: {error}", finish_reason="error")

                data = await resp.json()
                choice = data["choices"][0]
                message = choice["message"]

                # Handle native tool calls from vLLM
                raw_tool_calls = message.get("tool_calls")
                tool_calls = None
                if raw_tool_calls:
                    # Normalize to our format with repair
                    normalized = []
                    for tc in raw_tool_calls:
                        func = tc.get("function", {})
                        raw_args = func.get("arguments", "{}")
                        if isinstance(raw_args, str):
                            args = repair_truncated_tool_call(raw_args)
                        elif isinstance(raw_args, dict):
                            args = raw_args
                        else:
                            args = {}
                        normalized.append({
                            "tool": func.get("name", ""),
                            "params": args,
                        })
                    tool_calls = normalized

                raw_content = message.get("content", "") or ""
                clean_content = strip_think_blocks(raw_content)

                if check_empty_response(clean_content, tool_calls):
                    return LLMResponse(
                        text="Error: Empty response from model",
                        finish_reason="error",
                    )

                return LLMResponse(
                    text=clean_content,
                    tool_calls=tool_calls,
                    finish_reason="tool_calls" if tool_calls else choice.get("finish_reason", "stop"),
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"vLLM request failed: {e}")
            return LLMResponse(text=f"Error: {e}", finish_reason="error")

    async def stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream tokens from vLLM via SSE."""
        await self._ensure_session()

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        try:
            async with self._session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            ) as resp:
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if not line_str or not line_str.startswith("data: "):
                        continue
                    data_str = line_str[len("data: "):]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"vLLM stream failed: {e}")
            yield f"Error: {e}"


# System prompt for Velvet
VELVET_SYSTEM_PROMPT = """You are Velvet, a personal AI assistant. You are helpful, concise, and friendly.

You have access to various skills and can help with tasks like:
- Telling time and managing schedules
- Remembering information
- Answering questions
- Controlling devices and systems (when enabled)

Keep your responses brief and conversational since they will be spoken aloud.
If you don't know something, say so honestly.
When asked to do something you can't do, explain what you would need to accomplish it.
"""


def create_llm_adapter(
    adapter_type: str = "ollama",
    **kwargs,
) -> LLMAdapter:
    """Factory function to create an LLM adapter."""
    if adapter_type == "ollama":
        return OllamaAdapter(**kwargs)
    elif adapter_type == "llama.cpp":
        return LlamaCppAdapter(**kwargs)
    elif adapter_type == "vllm":
        return VLLMAdapter(**kwargs)
    elif adapter_type in ("google", "universal"):
        from velvet.services.universal_llm import UniversalCloudLLMAdapter
        provider = kwargs.pop("provider", "google") if adapter_type == "universal" else "google"
        return UniversalCloudLLMAdapter(provider=provider, **kwargs)
    else:
        raise LLMAdapterError(f"Unknown adapter type: {adapter_type}")


_default_adapter: LLMAdapter | None = None

def set_default_adapter(adapter: LLMAdapter) -> None:
    """Set the default LLM adapter singleton."""
    global _default_adapter
    _default_adapter = adapter


def get_llm_adapter() -> LLMAdapter:
    """Get or create the default LLM adapter (singleton)."""
    global _default_adapter
    if _default_adapter is None:
        from velvet.config import get_config
        cfg = get_config()
        kwargs = {"model": cfg.llm.model}
        if cfg.llm.adapter in ("ollama", "vllm"):
            kwargs["base_url"] = cfg.llm.base_url
        _default_adapter = create_llm_adapter(cfg.llm.adapter, **kwargs)
    return _default_adapter
