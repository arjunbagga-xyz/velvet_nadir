import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock
from velvet.shen.hun import Hun
from velvet.skills import get_skill_registry, skill, SkillCategory, SkillParameter, SkillResult

class TestHunAgentic(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Register a dummy skill for testing
        @skill(
            name="test_tool",
            description="A tool for testing agentic behavior",
            category=SkillCategory.DIGITAL,
            parameters=[
                SkillParameter("query", "string", "The test query")
            ]
        )
        async def test_tool(query: str):
            return SkillResult.ok(data=f"Saw query: {query}")
        
        self.hun = Hun()
        # Mock the inference callable manually
        self.mock_llm = AsyncMock()
        self.hun.set_llm_inference(self.mock_llm)
        
    async def test_reason_injects_tools(self):
        # Mock response from LLM
        self.mock_llm.return_value = '{"tool": "test_tool", "params": {"query": "hello world"}}'
        
        response = await self.hun.reason(context="Ambient noise.", task="Run the test tool with hello world.")
        
        # Verify the prompt contained the tool description
        args, kwargs = self.mock_llm.call_args
        prompt = args[0]
        
        self.assertIn("Available Tools:", prompt)
        self.assertIn("test_tool", prompt)
        self.assertIn("A tool for testing agentic behavior", prompt)
        self.assertIn('{"tool": "test_tool", "params": {"query": "hello world"}}', response)

if __name__ == "__main__":
    unittest.main()
