"""
AST-Based Safe Skill Discovery for Velvet Nadir.

Statically parses Python files using Python's `ast` module to locate and extract
metadata from `@skill` decorated functions WITHOUT importing or executing untrusted code.
Caches parsed definitions keyed by (st_mtime_ns, st_size) for instantaneous reload checks.
"""

import ast
from pathlib import Path
from typing import Any, Optional
from loguru import logger

# In-memory mtime cache: {path: (mtime_ns, size, [parsed_definitions])}
_AST_CACHE: dict[str, tuple[int, int, list[dict[str, Any]]]] = {}


def parse_skill_file(file_path: Path | str) -> list[dict[str, Any]]:
    """
    Statically parse a Python file for @skill decorated functions.

    Returns a list of extracted skill metadata dictionaries:
    [
        {
            "name": "...",
            "description": "...",
            "category": "...",
            "parameters": [...],
            "tags": [...],
            "file": "...",
            "line": int
        },
        ...
    ]
    """
    path = Path(file_path)
    if not path.is_file() or not path.name.endswith(".py"):
        return []

    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
        size = stat.st_size
    except OSError as e:
        logger.debug(f"[SkillDiscovery] Could not stat {path}: {e}")
        return []

    path_key = str(path.resolve())
    if path_key in _AST_CACHE:
        cached_mtime, cached_size, cached_skills = _AST_CACHE[path_key]
        if cached_mtime == mtime_ns and cached_size == size:
            return cached_skills

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except Exception as e:
        logger.warning(f"[SkillDiscovery] Failed to parse AST for {path}: {e}")
        return []

    skills_found: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        skill_decorator = _find_skill_decorator(node)
        if not skill_decorator:
            continue

        metadata = _extract_decorator_metadata(skill_decorator, node, path)
        if metadata:
            skills_found.append(metadata)

    _AST_CACHE[path_key] = (mtime_ns, size, skills_found)
    return skills_found


def _find_skill_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[ast.Call]:
    """Find @skill(...) or @velvet.skill(...) decorator call."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Name) and func.id == "skill":
                return dec
            if isinstance(func, ast.Attribute) and func.attr == "skill":
                return dec
    return None


def _extract_decorator_metadata(
    dec: ast.Call,
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    path: Path,
) -> dict[str, Any]:
    """Extract metadata from the @skill decorator call arguments."""
    metadata: dict[str, Any] = {
        "name": func_node.name,
        "description": ast.get_docstring(func_node) or "",
        "category": "digital",
        "parameters": [],
        "tags": [],
        "file": str(path),
        "line": func_node.lineno,
    }

    # Positional args in @skill(name, description, category, ...)
    pos_fields = ["name", "description", "category"]
    for i, arg in enumerate(dec.args):
        if i < len(pos_fields):
            val = _extract_literal_val(arg)
            if val is not None:
                metadata[pos_fields[i]] = str(val)

    # Keyword args in @skill(name="...", description="...", category=...)
    for kw in dec.keywords:
        if kw.arg in ("name", "description", "category"):
            val = _extract_literal_val(kw.value)
            if val is not None:
                metadata[kw.arg] = str(val)
        elif kw.arg == "tags":
            val = _extract_literal_val(kw.value)
            if isinstance(val, list):
                metadata["tags"] = [str(t) for t in val]

    # Extract function argument names as parameters
    params = []
    for arg in func_node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        params.append({
            "name": arg.arg,
            "type": _extract_annotation(arg.annotation) if arg.annotation else "string",
        })
    if params:
        metadata["parameters"] = params

    return metadata


def _extract_literal_val(node: ast.AST) -> Any:
    """Safely extract literal values from AST without eval()."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Attribute):
        # e.g., SkillCategory.PERCEPTION -> 'perception'
        return node.attr.lower()
    elif isinstance(node, ast.List):
        return [_extract_literal_val(elt) for elt in node.elts]
    return None


def _extract_annotation(node: ast.AST) -> str:
    """Extract argument type annotation as string."""
    if isinstance(node, ast.Name):
        return node.id.lower()
    elif isinstance(node, ast.Constant):
        return str(node.value).lower()
    return "string"


def discover_skills_in_directory(dir_path: Path | str) -> list[dict[str, Any]]:
    """Recursively scan a directory for @skill decorated functions via AST."""
    directory = Path(dir_path)
    if not directory.is_dir():
        return []

    discovered = []
    for py_file in directory.rglob("*.py"):
        skills = parse_skill_file(py_file)
        discovered.extend(skills)
    return discovered
