import pytest
import textwrap
from velvet.config import load_config

class TestConfigLoading:
    """Tests for config loading, validation, and overrides."""

    def test_toml_config_loading(self, tmp_path):
        """Verify that load_config reads basic fields from velvet.toml."""
        toml_path = tmp_path / "velvet.toml"
        toml_path.write_text(textwrap.dedent('''
            [velvet]
            device_id = "toml-device"
            [velvet.llm]
            adapter = "vllm"
        '''))
        
        cfg = load_config(config_path=toml_path)
        assert cfg.device_id == "toml-device"
        assert cfg.llm.adapter == "vllm"

    def test_toml_env_priority(self, tmp_path, monkeypatch):
        """Verify that Env Vars override TOML values."""
        toml_path = tmp_path / "velvet.toml"
        toml_path.write_text('device_id = "toml-device"')
        
        monkeypatch.setenv("VELVET_DEVICE_ID", "env-device")
        
        cfg = load_config(config_path=toml_path)
        assert cfg.device_id == "env-device"


class TestConfigDeepMerge:
    """Tests for config loading deep merging and manual overrides."""

    def test_override_beats_file(self, tmp_path):
        """Manual overrides take highest priority over TOML."""
        toml_path = tmp_path / "velvet.toml"
        toml_path.write_text(textwrap.dedent('''
            [velvet]
            device_id = "toml-id"
        '''))

        cfg = load_config(config_path=toml_path, device_id="override-id")
        assert cfg.device_id == "override-id"

    def test_nested_override(self, tmp_path):
        """Override works for nested subsystem configs."""
        toml_path = tmp_path / "velvet.toml"
        toml_path.write_text(textwrap.dedent('''
            [velvet.security]
            mesh_secret = "toml-secret"
        '''))

        cfg = load_config(
            config_path=toml_path,
            security={"mesh_secret": "override-secret"}
        )
        assert cfg.security.mesh_secret == "override-secret"

    def test_file_defaults_preserved(self, tmp_path):
        """Fields not overridden keep their file/default values."""
        toml_path = tmp_path / "velvet.toml"
        toml_path.write_text(textwrap.dedent('''
            [velvet]
            device_id = "toml-node"
            [velvet.llm]
            adapter = "vllm"
            model = "llama-70b"
        '''))

        cfg = load_config(config_path=toml_path)
        assert cfg.device_id == "toml-node"
        assert cfg.llm.adapter == "vllm"
        assert cfg.llm.model == "llama-70b"
        # Default preserved
        assert cfg.llm.base_url == "http://localhost:11434"
