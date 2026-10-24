"""
Business Paradigm Skill

Allows a CEO agent to spawn task graphs, delegate tasks to sub-agents, and track progress.
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from loguru import logger
import asyncio
from velvet.skills.base import Skill
from velvet.task_graph import TaskGraph, TaskState

class TaskDef(BaseModel):
    name: str
    description: str
    dependencies: List[str] = Field(default_factory=list)
    assignee: str = None

class BusinessParadigmParams(BaseModel):
    action: str = Field(default="init_business", description="Action to perform: 'init_business', 'create_graph', 'add_task', 'assign', 'update_status', 'status', 'spawn_agent', 'request_delegation'")
    tasks: List[TaskDef] = Field(default=None, description="Tasks to add to graph (for create_graph/add_task)")
    task_id: str = Field(default=None, description="Task ID for assign/update_status")
    agent_id: str = Field(default=None, description="Agent ID for assign/spawn_agent")
    agent_type: str = Field(default="worker", description="Type of agent for spawn_agent")
    parent_id: str = Field(default="yi", description="Parent agent ID for spawn_agent")
    capabilities: List[str] = Field(default=None, description="Capabilities list for spawn_agent")
    request_type: str = Field(default=None, description="Request type for request_delegation ('spawn_subagent', 'budget_request')")
    status: str = Field(default=None, description="Status to update (completed, failed)")
    result: str = Field(default=None, description="Result payload")

from velvet.skills.base import Skill, SkillDefinition, SkillCategory, SkillParameter, SkillResult, get_skill_registry

class BusinessParadigmSkill(Skill):
    """
    Skill for autonomous agents to manage goal-driven tasks.
    """
    
    def __init__(self, fabric=None, agents_manager=None):
        super().__init__()
        self.fabric = fabric
        self.agents_manager = agents_manager
        self.agents_manager = agents_manager

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="business_paradigm",
            description="Manage Task Graphs, delegate tasks to sub-agents, spawn agents, and track progress.",
            category=SkillCategory.SPECIALIST,
            parameters=[
                SkillParameter("action", "string", "Action to perform ('create_graph', 'add_task', 'assign', 'update_status', 'status', 'spawn_agent', 'request_delegation')"),
                SkillParameter("agent_id", "string", "Agent ID", required=False),
                SkillParameter("task_id", "string", "Task ID", required=False),
                SkillParameter("agent_type", "string", "Agent type for spawn_agent", required=False, default="worker"),
                SkillParameter("request_type", "string", "Request type for request_delegation", required=False),
                SkillParameter("status", "string", "Status update", required=False),
            ]
        )

    async def execute(self, params: Dict[str, Any] | None = None, **kwargs) -> SkillResult:
        merged = {}
        if isinstance(params, dict):
            merged.update(params)
        merged.update(kwargs)
        
        p = BusinessParadigmParams(**merged)
        
        if not self.agents_manager:
            try:
                from velvet.gateway import get_gateway
                self.agents_manager = get_gateway().agent_orchestrator
            except Exception:
                pass
                
        if not self.agents_manager:
            return SkillResult.fail("No agents_manager provided.")

        if p.action == "init_business":
            from velvet.context import get_context_manager, TrackType
            ctx_mgr = get_context_manager()
            project_context = ""
            if TrackType.PROJECT in ctx_mgr.tracks:
                project_context = ctx_mgr.tracks[TrackType.PROJECT].state.get("goal", str(ctx_mgr.tracks[TrackType.PROJECT].state))

            astra_persona = (
                "You are Astra, the CEO of a newly formed Tycoon-style autonomous business agency. "
                "Your job is to act as the central manager, break down the overarching Project Context into a directed TaskGraph, "
                "and delegate tasks to specialized sub-agents (e.g., Darren for Software Delivery, Casey for Creative, Harper for Legal). "
                "IMPORTANT: If the Project Context is ambiguous or unclear, you MUST immediately halt and ask the user for clarification before spawning any other agents. "
                "You report directly to the user."
            )
            
            identity = self.agents_manager.spawn_worker(
                agent_id="astra",
                agent_type="ceo",
                parent_id="yi",
                capabilities=["task_graph_management", "delegation", "business_strategy"],
                custom_fields={"system_prompt": astra_persona}
            )
            return SkillResult.ok(data={
                "message": f"Business paradigm initialized. Astra (CEO) spawned.", 
                "agent_id": "astra",
                "context": project_context
            })

        elif p.action == "create_graph":
            task_ids = []
            if p.tasks:
                for t in p.tasks:
                    node = self.agents_manager.add_graph_task(t.name, t.description, t.dependencies)
                    if t.assignee:
                        await self.agents_manager.assign_graph_task(node.id, t.assignee)
                    task_ids.append(node.id)
            return SkillResult.ok(data={"message": "Task graph created", "task_ids": task_ids})
            
        elif p.action == "add_task":
            task_ids = []
            if p.tasks:
                for t in p.tasks:
                    node = self.agents_manager.add_graph_task(t.name, t.description, t.dependencies)
                    if t.assignee:
                        await self.agents_manager.assign_graph_task(node.id, t.assignee)
                    task_ids.append(node.id)
            return SkillResult.ok(data={"message": "Tasks added", "task_ids": task_ids})
            
        elif p.action == "assign":
            if not p.task_id or not p.agent_id:
                return SkillResult.fail("Missing task_id or agent_id")
            await self.agents_manager.assign_graph_task(p.task_id, p.agent_id)
            return SkillResult.ok(data={"message": f"Task {p.task_id} assigned to {p.agent_id}"})
            
        elif p.action == "spawn_agent":
            if not p.agent_id:
                return SkillResult.fail("Missing agent_id for spawn_agent")
            
            identity = self.agents_manager.spawn_worker(
                agent_id=p.agent_id,
                agent_type=p.agent_type,
                parent_id=p.parent_id,
                capabilities=p.capabilities
            )
            return SkillResult.ok(data={"message": f"Agent {identity.agent_id} spawned successfully", "agent_id": identity.agent_id})

        elif p.action == "request_delegation":
            if not p.agent_id or not p.request_type:
                return SkillResult.fail("Missing agent_id or request_type")
                
            res = await self.agents_manager.handle_delegation_request(
                from_agent_id=p.agent_id,
                request_type=p.request_type,
                details={"sub_agent_id": p.task_id, "capabilities": p.capabilities}
            )
            return SkillResult.ok(data={"delegation_result": res})

        elif p.action == "update_status":
            if not p.task_id or not p.status:
                return SkillResult.fail("Missing task_id or status")
            
            state_map = {
                "completed": TaskState.COMPLETED,
                "failed": TaskState.FAILED,
                "in_progress": TaskState.IN_PROGRESS
            }
            if p.status not in state_map:
                return SkillResult.fail("Invalid status")
                
            self.agents_manager.update_graph_task_state(p.task_id, state_map[p.status], p.result)
            return SkillResult.ok(data={"message": f"Task {p.task_id} updated to {p.status}"})
            
        elif p.action == "status":
            summary = []
            for t_id, t in self.agents_manager.task_graph.tasks.items():
                summary.append({
                    "id": t_id,
                    "name": t.name,
                    "state": t.state.value,
                    "assignee": t.assignee,
                    "dependencies": t.dependencies
                })
            return SkillResult.ok(data={"tasks": summary})
            
        return SkillResult.fail("Unknown action")


# Register the skill
from velvet.skills.base import get_skill_registry
get_skill_registry().register(BusinessParadigmSkill())

