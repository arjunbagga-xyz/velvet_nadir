"""
Armature Preprocessor.

Performs parameter interpolation and config injection for skill executions.
"""

__all__ = [
    "Armature",
]

import os
import re
from loguru import logger
from typing import Any
from velvet.config import get_config
from .base import Skill


class Armature:
    """
    Armature Preprocessor.
    
    Preprocesses skill parameters before execution:
    1. Injects configured keys requested by the skill.
    2. Interpolates template strings: {{env.VAR}}, {{device.id}}, etc.
    """

    @staticmethod
    def preprocess(skill: Skill, params: dict) -> dict:
        """Preprocess parameters for the given skill, returning a new dictionary."""
        config = get_config()
        processed = params.copy()

        # 1. Config Injection
        config_dict = {}
        for path in skill.definition.requires_config:
            val = Armature._get_config_path(config, path)
            if val is not None:
                # Expose both nested and flattened keys for convenience
                config_dict[path] = val
                flat_key = f"config_{path.replace('.', '_')}"
                processed[flat_key] = val
                logger.debug(f"[Armature] Injected config {path} into parameter: {flat_key}")
        
        if config_dict:
            processed["config"] = config_dict

        # 2. Variable Interpolation
        for k, v in list(processed.items()):
            if isinstance(v, str):
                processed[k] = Armature._interpolate_string(v, config)
            elif isinstance(v, list):
                processed[k] = [
                    Armature._interpolate_string(item, config) if isinstance(item, str) else item
                    for item in v
                ]
            elif isinstance(v, dict):
                processed[k] = {
                    key: Armature._interpolate_string(val, config) if isinstance(val, str) else val
                    for key, val in v.items()
                }

        return processed

    @staticmethod
    def _get_config_path(config, path: str) -> Any:
        """Safely traverse a dotted path in Pydantic settings config."""
        parts = path.split(".")
        current = config
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                logger.warning(f"[Armature] Config path not found: {path} (failed at {part})")
                return None
        return current

    @staticmethod
    def _interpolate_string(text: str, config) -> str:
        """Replace template placeholders and evaluate inline shell commands."""
        # 1. Interpolate Environment and Config variables: {env.VAR}, {{env.VAR}}, {config.foo}, {{config.foo}}, {VAR}, {{VAR}}
        def replace_var(match):
            prefix = match.group(1)
            var_name = match.group(2)
            
            if prefix == "env":
                return os.environ.get(var_name, "")
            elif prefix == "config":
                val = Armature._get_config_path(config, var_name)
                return str(val) if val is not None else ""
            else:
                if var_name in ("device.id", "device_id"):
                    return str(getattr(config, "device_id", "unknown"))
                if var_name in ("user.name", "user"):
                    return "user"
                if var_name in os.environ:
                    return os.environ[var_name]
                val = Armature._get_config_path(config, var_name)
                if val is not None:
                    return str(val)
                return match.group(0)

        text = re.sub(r"\{{1,2}\s*(?:(env|config)\.)?([A-Za-z0-9_.-]+)\s*\}{1,2}", replace_var, text)

        # 2. Inline shell evaluation: $(command)
        def replace_shell(match):
            cmd = match.group(1).strip()
            allow_host = getattr(getattr(config, "security", {}), "allow_host_exec", False)
            if isinstance(config.security, dict):
                allow_host = config.security.get("allow_host_exec", False)
            else:
                allow_host = getattr(config.security, "allow_host_exec", False)
                
            if allow_host:
                import subprocess
                try:
                    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10.0)
                    return res.stdout.strip()
                except Exception as e:
                    logger.warning(f"[Armature] Host shell execution failed for '{cmd}': {e}")
                    return f"[Error: {e}]"
            else:
                # Sandboxed CUA container execution by default
                import urllib.request
                import json as json_lib
                endpoint = "http://localhost:8000/cua/action"
                payload = json_lib.dumps({"action": "execute_bash", "text": cmd, "target": "sandbox"}).encode("utf-8")
                req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=3.0) as resp:
                        if resp.status == 200:
                            data = json_lib.loads(resp.read().decode("utf-8"))
                            return str(data.get("stdout", "")).strip()
                except Exception as e:
                    logger.debug(f"[Armature] Sandbox server connection skipped, running simulation fallback: {e}")
                return f"Simulated output of: {cmd}"

        text = re.sub(r"\$\(([^)]+)\)", replace_shell, text)
        return text
