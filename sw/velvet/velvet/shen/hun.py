import logging
from velvet.config import get_config

logger = logging.getLogger(__name__)

class Hun:
    """
    Hun (魂): The Ethereal Soul / Mind.
    
    Handles Host capabilities: Deep Reasoning, Coding, Simulation, and Creativity.
    Receives its LLM adapter from the Gateway — does NOT own a private engine.
    Hun is a prompt builder, not an inference engine.
    """
    
    def __init__(self, llm_inference=None):
        """
        Args:
            llm_inference: Async callable (context, messages, tools) -> str
                          Provided by Gateway. Routes through mesh or fast-path.
        """
        self.config = get_config()
        self._llm_inference = llm_inference

    def set_llm_inference(self, llm_inference):
        """Set or update the LLM inference function (late binding from Gateway)."""
        self._llm_inference = llm_inference

    async def reason(self, context: str, task: str) -> str:
        """
        Deep thinking / detailed generation with tool awareness.
        """
        if not self._llm_inference:
            return "[Hun] No LLM inference available. Connect an LLM adapter."
            
        # 1. Retrieve total toolset from registry
        from velvet.skills import get_skill_registry
        registry = get_skill_registry()
        tools = registry.list_all()
        
        # 1b. Retrieve external MCP tools from LimenGateway
        from velvet.limen import get_limen_gateway
        limen = get_limen_gateway()
        mcp_tools = limen.mcp_tool_schemas
        
        # 2. Format tool descriptions for the prompt
        tool_desc = ""
        if tools or mcp_tools:
            tool_desc = "\nAvailable Tools:\n"
            for t in tools:
                params = ", ".join([f"{p.name} ({p.param_type})" for p in t.parameters])
                tool_desc += f"- {t.name}: {t.description}. Params: [{params}]\n"
            for t_name, t_info in mcp_tools.items():
                schema = t_info.get("schema", {}).get("function", {})
                desc = schema.get("description", "")
                tool_desc += f"- {t_name}: {desc}. Params: {schema.get('parameters', {})}\n"
                
            tool_desc += (
                "\nTo use a tool, respond with a JSON block like this:\n"
                "```json\n"
                '{"tool": "tool_name", "params": {"param1": "value1"}}\n'
                "```\n"
                "If no tool is needed, respond with plain text.\n"
            )

        # 3. Construct prompt and call LLM
        system_context = (
            f"You are the Hun (Mind) of Velvet Nadir. "
            f"Use the tools provided if necessary to fulfill the task. {tool_desc}\n"
            f"CTX: {context}"
        )
        messages = [{"role": "user", "content": task}]
        
        import time
        start_t = time.time()
        res = await self._llm_inference(system_context, messages, None)
        latency_ms = (time.time() - start_t) * 1000.0

        try:
            from velvet.shen.affinity import ModelAffinityTracker
            tracker = ModelAffinityTracker()
            model_name = getattr(self.config.llm, "model", "default_model")
            device_id = getattr(self.config, "device_id", "local")
            quality = 0.9 if res and not res.startswith("[Hun]") else 0.2
            await tracker.record_task_result(
                model=model_name,
                task_type="reasoning",
                quality=quality,
                latency_ms=latency_ms,
                device_id=device_id
            )
        except Exception as err:
            logger.debug(f"[Hun] Failed to record affinity result: {err}")

        return res

    async def imagine(self, prompt: str) -> str:
        """
        Creative generation (Code/Story).
        """
        if not self._llm_inference:
             return "[Hun] Imagination not available."
        
        messages = [{"role": "user", "content": prompt}]
        return await self._llm_inference("You are a creative AI assistant.", messages, None)
