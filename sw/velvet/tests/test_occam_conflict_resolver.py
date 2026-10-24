import pytest
import json
from velvet.config import get_config
from velvet.shen.jing import Jing
from velvet.shen.occam import OccamsRazorTask
from velvet.llm import LLMAdapter, LLMResponse


class MockLLMAdapter(LLMAdapter):
    """Mock LLM adapter to return custom JSON choices for conflict resolution."""
    def __init__(self):
        self.last_messages = None
        self.called_count = 0
        self.should_resolve = True
        self.decision = "merged"
        self.reconciled_fact = "Merged Fact Result"

    async def generate(self, messages, tools=None, max_tokens=1024, temperature=0.7):
        self.last_messages = messages
        self.called_count += 1
        
        response_dict = {
            "resolved": self.should_resolve,
            "decision": self.decision,
            "fact": self.reconciled_fact,
            "role": "user",
            "metadata": {"reconciled": True},
            "rationale": "Testing parsimonious merge"
        }
        return LLMResponse(text=json.dumps(response_dict))

    async def stream(self, messages, max_tokens=1024, temperature=0.7):
        raise NotImplementedError()


@pytest.fixture
def mock_llm(monkeypatch):
    mock = MockLLMAdapter()
    monkeypatch.setattr("velvet.shen.occam.get_llm_adapter", lambda: mock)
    return mock


@pytest.fixture
def clean_jing(tmp_path, monkeypatch):
    monkeypatch.setattr(get_config().memory, "tartarus_db_path", tmp_path / "tartarus_test.db")
    jing = Jing()
    return jing


@pytest.mark.asyncio
async def test_occam_no_conflicts(clean_jing, mock_llm):
    """Verify that OccamsRazorTask does nothing if there are no conflicts."""
    task = OccamsRazorTask(jing=clean_jing)
    await task.run([])
    
    assert mock_llm.called_count == 0


@pytest.mark.asyncio
async def test_occam_successful_resolution(clean_jing, mock_llm):
    """Verify successful LLM-mediated conflict resolution updates database status."""
    # Insert two conflicting transactions with the same ID but different details
    sutra_id = "device_x:10"
    
    sutra_a = {
        "id": sutra_id,
        "device_id": "device_x",
        "version_num": 10,
        "hash": "hash_a",
        "action": "add",
        "payload": {"fact": "User prefers tea.", "role": "user", "metadata": {}},
        "timestamp": "2026-07-06T10:00:00Z"
    }
    
    sutra_b = {
        "id": sutra_id,
        "device_id": "device_x",
        "version_num": 10,
        "hash": "hash_b",  # different hash triggers conflict
        "action": "add",
        "payload": {"fact": "User prefers coffee.", "role": "user", "metadata": {}},
        "timestamp": "2026-07-06T10:01:00Z"
    }
    
    # Write transactions
    clean_jing.replicate_sutra(sutra_a)
    # The second insertion under the same ID with a different hash triggers conflict marking
    clean_jing.replicate_sutra(sutra_b)
    
    # Confirm it's marked as unresolved conflict
    conflicts = clean_jing.get_unresolved_conflicts()
    assert len(conflicts) == 2
    assert conflicts[0]["status"] == "CONFLICT_UNRESOLVED"
    
    # Mock LLM to merge them
    mock_llm.should_resolve = True
    mock_llm.reconciled_fact = "User prefers tea and coffee."
    
    task = OccamsRazorTask(jing=clean_jing)
    await task.run([])
    
    # Verify LLM was called with the conflicting versions in prompt
    assert mock_llm.called_count == 1
    prompt_content = mock_llm.last_messages[1]["content"]
    assert "User prefers tea" in prompt_content
    assert "User prefers coffee" in prompt_content
    
    # Verify conflict status is now resolved ('ACTIVE') and payload updated
    conflicts_after = clean_jing.get_unresolved_conflicts()
    assert len(conflicts_after) == 0
    
    # Re-fetch transaction and assert payload fact matches the merged fact
    cursor = clean_jing._tartarus._db.execute("SELECT payload, status FROM sutras WHERE id = ?", (sutra_id,))
    row = cursor.fetchone()
    assert row["status"] == "ACTIVE"
    payload = json.loads(row["payload"])
    assert payload["fact"] == "User prefers tea and coffee."
    
    # Verify the merged fact was written to active memory
    memories = await clean_jing.recall("tea and coffee", deep=True)
    assert any("User prefers tea and coffee." in m for m in memories)


@pytest.mark.asyncio
async def test_occam_unresolved_reconciliation(clean_jing, mock_llm):
    """Verify that unresolved conflicts remain in CONFLICT_UNRESOLVED state."""
    sutra_id = "device_y:15"
    sutra_a = {
        "id": sutra_id, "device_id": "device_y", "version_num": 15, "hash": "h1", "action": "add",
        "payload": {"fact": "Fact 1", "role": "user", "metadata": {}}, "timestamp": "2026-07-06T10:00:00Z"
    }
    sutra_b = {
        "id": sutra_id, "device_id": "device_y", "version_num": 15, "hash": "h2", "action": "add",
        "payload": {"fact": "Fact 2", "role": "user", "metadata": {}}, "timestamp": "2026-07-06T10:01:00Z"
    }
    
    clean_jing.replicate_sutra(sutra_a)
    clean_jing.replicate_sutra(sutra_b)
    
    # Mock LLM to declare it unresolved (ambiguous)
    mock_llm.should_resolve = False
    
    task = OccamsRazorTask(jing=clean_jing)
    await task.run([])
    
    # Verify conflict remains unresolved in database
    conflicts_after = clean_jing.get_unresolved_conflicts()
    assert len(conflicts_after) == 2
    assert conflicts_after[0]["status"] == "CONFLICT_UNRESOLVED"
