import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from velvet.fabric import MessageType, VelvetMessage
from velvet.shen.skill_approval import SkillApprovalTask
from velvet.display import DisplayBridge
from velvet.config import get_config

@pytest.fixture
def temp_pending_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        pending_file = Path(tmpdir) / "pending_skills.json"
        yield pending_file

@pytest.mark.asyncio
async def test_skill_approval_task_emits_event(temp_pending_file):
    """Test that SkillApprovalTask reads pending skills and emits event."""
    # Write some pending skill
    pending_data = {
        "test_skill": {
            "name": "test_skill",
            "description": "Test description",
            "code": "def test_skill(): pass"
        }
    }
    temp_pending_file.write_text(json.dumps(pending_data))
    
    task = SkillApprovalTask()
    task._pending_file = temp_pending_file
    
    # Mock fabric publish
    mock_fabric = AsyncMock()
    with patch("velvet.shen.skill_approval.get_fabric", return_value=mock_fabric):
        await task.run([])
        
        # Verify event was published
        mock_fabric.publish.assert_called_once_with(
            MessageType.SKILL_PENDING_APPROVAL.value,
            {
                "skill_name": "test_skill",
                "description": "Test description",
                "proactive": True
            }
        )

@pytest.mark.asyncio
async def test_display_bridge_pending_endpoints(temp_pending_file):
    """Test GET and POST API endpoints for pending skills in DisplayBridge."""
    # Write some pending skill
    pending_data = {
        "test_skill": {
            "name": "test_skill",
            "description": "Test description",
            "code": "def test_skill(): pass"
        }
    }
    temp_pending_file.write_text(json.dumps(pending_data))
    
    # Setup DisplayBridge mock
    cfg = get_config()
    cfg.display.enabled = True
    
    # Patch storage directory to temp directory
    with patch("velvet.config.get_config") as mock_get_cfg:
        mock_cfg = MagicMock()
        mock_cfg.storage.data_dir = str(temp_pending_file.parent)
        mock_cfg.display.enabled = True
        mock_cfg.display.dashboard_path = None
        mock_get_cfg.return_value = mock_cfg
        
        bridge = DisplayBridge(
            config=mock_cfg.display,
            fabric=MagicMock(),
            registry=MagicMock(),
            context=MagicMock(),
            agents=MagicMock()
        )
        
        from aiohttp import web
        
        # Test GET
        req = MagicMock(spec=web.Request)
        resp = await bridge.get_pending_skills(req)
        assert resp.status == 200
        data = json.loads(resp.body.decode("utf-8"))
        assert len(data) == 1
        assert data[0]["name"] == "test_skill"

        # Test POST (Resolve - Approve)
        req = MagicMock(spec=web.Request)
        req.json = AsyncMock(return_value={"skill_name": "test_skill", "approved": True})
        
        # Mock Saraswati task resolution
        mock_saraswati = AsyncMock()
        mock_saraswati.resolve_pending_skill = AsyncMock(return_value=True)
        
        with patch("velvet.gateway.get_gateway") as mock_gw:
            gw = MagicMock()
            gw.xi._tasks = {"saraswati": mock_saraswati}
            mock_gw.return_value = gw
            
            resp = await bridge.resolve_pending_skill(req)
            assert resp.status == 200
            data = json.loads(resp.body.decode("utf-8"))
            assert data["success"] is True
            mock_saraswati.resolve_pending_skill.assert_called_once_with("test_skill", True)
