"""
Tests for Po Learned Reflexes.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from velvet.shen.po import LearnedReflex


class TestLearnedReflex:
    """Test LearnedReflex dataclass and serialization."""

    def test_to_dict(self):
        reflex = LearnedReflex(
            pattern="what time is it",
            skill_name="get_time",
            params_template={},
            confidence=0.8,
            examples=["what time is it", "time please"],
        )
        d = reflex.to_dict()
        assert d["pattern"] == "what time is it"
        assert d["skill_name"] == "get_time"
        assert d["confidence"] == 0.8
        assert len(d["examples"]) == 2

    def test_from_dict(self):
        data = {
            "pattern": "weather",
            "skill_name": "check_weather",
            "params_template": {"city": "default"},
            "confidence": 0.7,
            "examples": ["weather", "how's the weather"],
        }
        reflex = LearnedReflex.from_dict(data)
        assert reflex.skill_name == "check_weather"
        assert reflex.params_template == {"city": "default"}

    def test_roundtrip(self):
        original = LearnedReflex(
            pattern="lights",
            skill_name="home_control",
            params_template={"device": "lights"},
            confidence=0.9,
            examples=["turn on lights", "lights on"],
        )
        restored = LearnedReflex.from_dict(original.to_dict())
        assert restored.pattern == original.pattern
        assert restored.confidence == original.confidence
        assert restored.examples == original.examples


class TestPoLearnedReflexes:
    """Test Po's learned reflex learning, matching, and persistence."""

    @pytest.fixture
    def po(self, tmp_path):
        """Create a Po instance with mocked dependencies and tmp reflexes path."""
        with patch("velvet.shen.po.get_config") as mock_config, \
             patch("velvet.shen.po.cv2"), \
             patch("velvet.shen.po.VisionMonitor"), \
             patch("velvet.shen.po.VisionEngine"):
            cfg = MagicMock()
            cfg.llm.vision_model = "test"
            cfg.llm.base_url = "http://test"
            mock_config.return_value = cfg

            from velvet.shen.po import Po
            p = Po(start_vision_monitor=False)
            p._reflexes_path = tmp_path / "reflexes.json"
            return p

    def test_learn_new_reflex(self, po):
        """Learning a new pattern should add it."""
        po.learn_reflex("check the weather", "check_weather", {"city": "auto"})
        assert len(po._learned_reflexes) == 1
        assert po._learned_reflexes[0].skill_name == "check_weather"
        assert po._learned_reflexes[0].confidence == 0.5

    def test_reinforce_existing_reflex(self, po):
        """Re-learning the same pattern should increase confidence."""
        po.learn_reflex("check the weather", "check_weather")
        po.learn_reflex("check the weather", "check_weather")
        assert len(po._learned_reflexes) == 1
        assert po._learned_reflexes[0].confidence == 0.6  # 0.5 + 0.1

    def test_persist_to_disk(self, po):
        """Learning should save to JSON file."""
        po.learn_reflex("set alarm", "set_alarm", {"time": "7am"})
        assert po._reflexes_path.exists()
        data = json.loads(po._reflexes_path.read_text())
        assert len(data) == 1
        assert data[0]["skill_name"] == "set_alarm"

    def test_load_from_disk(self, po, tmp_path):
        """Should load reflexes from JSON on init."""
        data = [
            {
                "pattern": "news",
                "skill_name": "get_news",
                "params_template": {},
                "confidence": 0.8,
                "examples": ["news", "what's new"],
            }
        ]
        po._reflexes_path.write_text(json.dumps(data))
        po._load_reflexes()
        assert len(po._learned_reflexes) == 1
        assert po._learned_reflexes[0].skill_name == "get_news"

    def test_match_exact(self, po):
        """Exact match against examples should work."""
        po.learn_reflex("play music", "play_music")
        # Boost confidence above threshold
        for _ in range(3):
            po.learn_reflex("play music", "play_music")
        result = po._match_learned("play music")
        assert result is not None
        assert result.skill_name == "play_music"

    def test_match_substring(self, po):
        """Substring match should work if confidence is high enough."""
        po._learned_reflexes.append(LearnedReflex(
            pattern="play music",
            skill_name="play_music",
            params_template={},
            confidence=0.8,
            examples=["play music", "play some music"],
        ))
        result = po._match_learned("play some music please")
        assert result is not None

    def test_no_match_low_confidence(self, po):
        """Low confidence reflexes should not match."""
        po._learned_reflexes.append(LearnedReflex(
            pattern="play music",
            skill_name="play_music",
            params_template={},
            confidence=0.3,  # Below 0.4 threshold
            examples=["play music"],
        ))
        result = po._match_learned("play music")
        assert result is None

    def test_no_match_unrelated(self, po):
        """Unrelated input should not match."""
        po.learn_reflex("play music", "play_music")
        result = po._match_learned("what is quantum physics")
        assert result is None

    def test_multiple_reflexes(self, po):
        """Multiple learned reflexes should coexist."""
        po.learn_reflex("play music", "play_music")
        po.learn_reflex("check weather", "check_weather")
        po.learn_reflex("set alarm", "set_alarm")
        assert len(po._learned_reflexes) == 3
