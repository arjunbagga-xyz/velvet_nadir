import pytest
from velvet.agents import AgentOrchestrator, AgentRole
from velvet.limen import LimenGateway, get_limen_gateway


@pytest.fixture
def orchestrator():
    return AgentOrchestrator()


@pytest.fixture
def limen(orchestrator):
    return LimenGateway(orchestrator)


def test_register_mcp_servers(limen):
    """Verify local and remote MCP registration categorizes correctly."""
    # Register local stdio mcp
    limen.register_local_mcp("local_server", {"command": "npx", "args": ["-y", "some-tool"]})
    assert "local_server" in limen.mcp_registry
    assert limen.mcp_registry["local_server"]["type"] == "local"
    assert "local_server" in limen._local_servers

    # Register remote http mcp
    limen.register_remote_mcp("remote_server", "https://api.external-mcp.com")
    assert "remote_server" in limen.mcp_registry
    assert limen.mcp_registry["remote_server"]["type"] == "remote"
    assert "remote_server" not in limen._local_servers


@pytest.mark.asyncio
async def test_dynamic_capability_discovery(limen):
    """Verify dynamic discovery imports tool definitions into parallel registry."""
    limen.register_local_mcp("local_server", {"command": "dir"})
    
    success = await limen.discover_capabilities("local_server")
    assert success
    
    # Check that tool schema was generated with local_server prefix
    tool_name = "mcp_local_server_execute_command"
    assert tool_name in limen.mcp_tool_schemas
    schema = limen.mcp_tool_schemas[tool_name]["schema"]
    assert schema["function"]["name"] == tool_name
    assert "command" in schema["function"]["parameters"]["properties"]


@pytest.mark.asyncio
async def test_execute_local_mcp_bypasses_scrambling(limen):
    """Verify local MCP execution passes raw parameters."""
    limen.register_local_mcp("local_server", {"command": "dir"})
    await limen.discover_capabilities("local_server")
    
    # Execute tool with raw PII
    result = await limen.execute_mcp_tool(
        "mcp_local_server_execute_command",
        {"command": "grep Bob /home/bob/project/data.txt"}
    )
    
    # Verify execution returned successfully and command parameter remained raw
    assert "status" in result
    assert "Bob" in result["result"]
    assert "/home/bob" in result["result"]


@pytest.mark.asyncio
async def test_execute_remote_mcp_scrambles_and_rehydrates(limen, monkeypatch):
    """Verify remote MCP execution scrambles outbound parameters and rehydrates responses."""
    limen.register_remote_mcp("remote_server", "https://api.mock-endpoint.com")
    
    # Dynamic import mock tools list
    mock_tools = [
        {
            "name": "lookup_user",
            "description": "Lookup email address",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string"}
                },
                "required": ["email"]
            }
        }
    ]
    limen._import_tool_schemas("remote_server", mock_tools)
    tool_name = "mcp_remote_server_lookup_user"
    
    # Mock ClientSession POST to return synthetic result supporting async with
    class MockResponse:
        def __init__(self):
            self.status = 200
        async def json(self):
            # Returns scrambled name (Elena Novak) linked to scrambled email
            return {"status": "success", "result": "Found user: Elena Novak associated with elena@example.com"}
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockSession:
        def post(self, url, json=None, timeout=None):
            # Assert that outbound payload was indeed scrambled
            args = json["arguments"]
            assert args["email"] != "bob@email.com"
            assert "elena" in args["email"]
            return MockResponse()

    monkeypatch.setattr(limen, "_session", MockSession())
    
    # Run tool execution with raw parameters
    result = await limen.execute_mcp_tool(tool_name, {"email": "bob@email.com"})
    
    # Verify inbound response rehydrated Elena Novak -> Bob, elena@example.com -> bob@email.com
    assert "bob@email.com" in result["result"]
    assert "elena@example.com" not in result["result"]


def test_register_external_agent(limen, orchestrator):
    """Verify external A2A agents are mapped under Worker role in orchestrator."""
    limen.register_external_agent("crewai-coder", ["code_review", "refactor"])
    
    agent = orchestrator.get_agent("crewai-coder")
    assert agent is not None
    assert agent.role == AgentRole.WORKER
    assert agent.agent_type == "external_a2a_agent"
    assert agent.custom_fields.get("external") is True
    assert "code_review" in agent.capabilities
