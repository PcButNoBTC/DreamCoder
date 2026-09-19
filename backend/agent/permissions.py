from __future__ import annotations

import os
from pathlib import Path

SAFE_COMMANDS = {
    "python", "python3", "pytest", "pip", "git", "npm", "node", "uv", "ruff", "mypy", "pyright", "go", "cargo", "rustc"
}

class PermissionError(RuntimeError):
    pass

def workspace_path(root: str, path: str) -> Path:
    base = Path(root).expanduser().resolve()
    candidate = (base / path).resolve() if not Path(path).is_absolute() else Path(path).expanduser().resolve()
    if candidate != base and base not in candidate.parents:
        raise PermissionError(f"Path escapes workspace: {path}")
    return candidate

def command_allowed(command: str) -> bool:
    parts = command.strip().split()
    if not parts:
        return False
    executable = Path(parts[0]).name.lower()
    return executable in SAFE_COMMANDS

def require_write_approval(auto_apply: bool) -> None:
    if not auto_apply:
        raise PermissionError("Write operations require explicit approval (set auto_apply=true only for trusted local runs).")
