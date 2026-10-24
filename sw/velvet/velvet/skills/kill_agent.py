"""
Kill Agent Skill

Allows the system to dynamically terminate an agent and clean up its resources.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field
from velvet.skills.base import Skill, SkillDefinition, SkillCategory, SkillParameter, SkillResult, get_skill_registry
from loguru import logger

class KillAgentParams(BaseModel):
    agent_id: str = Field(..., description="The ID of the agent to terminate")

class KillAgentSkill(Skill):
    """
    Skill to terminate a dynamic agent and clean up its resources.
    """
    
    def __init__(self, agents_manager=None):
        super().__init__()
        self.agents_manager = agents_manager

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="kill_agent",
            description="Terminate a dynamic agent, cancel its background tasks, and remove it from the roster.",
            category=SkillCategory.DIGITAL,
            parameters=[
                SkillParameter("agent_id", "string", "The ID of the agent to terminate (e.g., 'astra')"),
            ]
        )

    async def execute(self, params: Dict[str, Any] | None = None, **kwargs) -> SkillResult:
        merged = {}
        if isinstance(params, dict):
            merged.update(params)
        merged.update(kwargs)
        
        try:
            p = KillAgentParams(**merged)
        except Exception as e:
            return SkillResult.fail(f"Invalid parameters: {e}")
        
        if not self.agents_manager:
            try:
                from velvet.gateway import get_gateway
                self.agents_manager = get_gateway().agent_orchestrator
            except Exception:
                pass

        if not self.agents_manager:
            return SkillResult.fail("No agents_manager provided to KillAgentSkill.")
            
        success = self.agents_manager.kill_worker(p.agent_id)
        if success:
            logger.info(f"Agent {p.agent_id} successfully terminated via KillAgentSkill.")
            return SkillResult.ok(data={"message": f"Agent {p.agent_id} successfully terminated."})
        else:
            logger.warning(f"Failed to terminate agent {p.agent_id}. Agent not found.")
            return SkillResult.fail(f"Agent {p.agent_id} not found or could not be terminated.")

# Register the skill
get_skill_registry().register(KillAgentSkill())
