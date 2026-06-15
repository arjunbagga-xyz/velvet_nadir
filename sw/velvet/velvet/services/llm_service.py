"""
LLM Service Provider.

Wraps a local LLM backend (via Polymath) and exposes it to the Velvet Mesh.
Participates in Smart Routing by broadcasting real-time load stats.
"""

import asyncio
import json
import time
from typing import Any
from datetime import datetime, timezone
from loguru import logger

from velvet.config import get_config
from velvet.fabric import get_fabric, MessageType, VelvetMessage
from velvet.shen.polymath import Polymath, HardwareType, InferenceBackend
from velvet.devices import DeviceLoad, get_registry
from velvet.llm import LLMAdapter, LLMResponse, create_llm_adapter

class LLMProvider:
    """
    Service that provides LLM capabilities to the mesh.
    
    Responsibilities:
    1. Load local LLM using Polymath logic.
    2. Listen for 'velvet/mesh/llm/request/{my_id}'.
    3. Execute inference.
    4. Track 'active_tasks' and update local Device state.
    """
    
    def __init__(self):
        self.config = get_config()
        self.fabric = get_fabric()
        self.poly = Polymath()
        self.backend = None
        self.device_id = self.config.zenoh.device_id
        self._active_tasks = 0
        self._lock = asyncio.Lock()
        
    async def start(self):
        """Start the LLM Provider service."""
        logger.info(f"[LLMService] Starting on device {self.device_id}...")
        
        # 1. Initialize Backend
        # Logic: If we are a Compute Node (Host), try to load the heavy model.
        # For MVP, we respect the config 'adapter' setting but wrap it in mesh service.
        try:
            # 1. Resolve adapter type via Polymath if 'auto'
            adapter_type = self.config.llm.adapter
            if adapter_type == "auto":
                adapter_type = self.poly.inference_backend
            
            model = self.config.llm.model
            
            # 2. Integrate with Polymath for creation
            # If it's a high-performance local backend, use Polymath's specific logic.
            # Route to Polymath if explicitly set to local/in-process types, or if the model path exists locally.
            from pathlib import Path
            is_local_path = False
            try:
                is_local_path = Path(model).exists()
            except Exception:
                pass

            if adapter_type in ("llama.cpp", "tensorrt", "vllm-local") or (adapter_type == "vllm" and is_local_path):
                # Use Polymath's create_backend which knows about VRAM, CUDA, etc.
                backend = self.poly.create_backend(model)
                
                # Wrap it to fulfill the LLMAdapter interface used by this service
                self.backend = PolymathAdapterWrapper(backend, model)
                logger.info(f"[LLMService] High-perf backend loaded via Polymath: {adapter_type} ({model})")
            else:
                # Fallback to standard network or hosted adapters
                kwargs = {"model": model}
                if adapter_type in ("ollama", "vllm"):
                    kwargs["base_url"] = self.config.llm.base_url
                elif adapter_type == "google":
                    kwargs["api_key"] = self.config.llm.google_api_key

                self.backend = create_llm_adapter(adapter_type, **kwargs)
                logger.info(f"[LLMService] Backend loaded via factory: {adapter_type}/{model}")
            
        except Exception as e:
            logger.error(f"[LLMService] Failed to load backend: {e}")
            return

        # 2. Subscribe to Requests (Unicast)
        # Topic: velvet/mesh/llm/request/<device_id>
        topic = f"velvet/mesh/llm/request/{self.device_id}"
        await self.fabric.subscribe(topic, self._on_request)
        logger.info(f"[LLMService] Listening on {topic}")
        
        # 3. Publish Capability (One-off announce, plus periodic via heartbeat)
        # We don't strictly need a separate announce if heartbeat covers it,
        # but let's be explicit. (Refinement for later)

    async def stop(self):
        """Stop the LLM Provider service."""
        self.backend = None
        logger.info("[LLMService] Stopped")

    async def _on_request(self, msg: VelvetMessage):
        """Handle incoming LLM request."""
        payload = msg.payload
        reply_to = payload.get("reply_to")
        request_id = payload.get("request_id")
        messages = payload.get("messages", [])
        tools = payload.get("tools")
        
        logger.info(f"[LLMService] Received request {request_id} from {msg.source_device}")
        
        # 1. Update Load (BUSY)
        await self._update_load(1)
        
        try:
            # 2. Execute
            start_t = time.perf_counter()
            response = await self.backend.generate(messages, tools=tools)
            duration = time.perf_counter() - start_t
            
            # 3. Reply
            if reply_to:
                reply_payload = {
                    "request_id": request_id,
                    "text": response.text,
                    "tool_calls": response.tool_calls,
                    "tokens_used": response.tokens_used,
                    "duration": duration,
                    "model": self.config.llm.model
                }
                
                # Publish to reply topic
                # Topic: velvet/mesh/llm/response/<request_id> (or direct to device)
                # Let's use the specific reply topic requested
                await self.fabric.publish(reply_to, reply_payload)
                logger.info(f"[LLMService] Reply sent to {reply_to} ({duration:.2f}s)")
                
        except Exception as e:
            logger.error(f"[LLMService] Inference failed: {e}")
            if reply_to:
                 await self.fabric.publish(reply_to, {"request_id": request_id, "error": str(e)})
        finally:
            # 4. Update Load (IDLE)
            await self._update_load(-1)

    async def _update_load(self, delta: int):
        """Update active task count and broadcast heartbeat."""
        async with self._lock:
            self._active_tasks += delta
            # Clamp to 0
            if self._active_tasks < 0: self._active_tasks = 0
            
            # Update local registry entry (if exists)
            try:
                registry = get_registry()
                device = registry.get_device(self.device_id)
                if device:
                    device.load.active_tasks = self._active_tasks
                    
                    # Force a heartbeat broadcast immediately to inform the mesh
                    # Construct heartbeat payload
                    hb_payload = {
                        "device_id": self.device_id,
                        "status": "online",
                        "load": device.load.to_dict()
                    }
                    await self.fabric.publish(MessageType.MESH_DEVICE_HEARTBEAT.value, hb_payload)
                    # logger.debug(f"[LLMService] Load broadcast: active_tasks={self._active_tasks}")
            except Exception:
                pass

class PolymathAdapterWrapper(LLMAdapter):
    """Wraps Polymath's InferenceBackend to match the LLMAdapter interface."""
    def __init__(self, backend: InferenceBackend, model_name: str):
        self._backend = backend
        self._model_name = model_name
        
    async def generate(self, messages, tools=None, **kwargs) -> LLMResponse:
        # Simple prompt construction for the raw backend
        prompt = ""
        for m in messages:
            role = m.get("role", "user").capitalize()
            content = m.get("content", "")
            prompt += f"{role}: {content}\n"
        prompt += "Assistant: "
        
        text = await self._backend.generate(prompt, **kwargs)
        return LLMResponse(text=text)

    async def stream(self, messages, **kwargs):
        # Fallback to non-streaming for now as InferenceBackend doesn't support it yet
        response = await self.generate(messages, **kwargs)
        yield response.text
