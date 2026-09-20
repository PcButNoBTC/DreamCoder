"""Canonical project workspace and Git runtime for DreamCoder."""

from __future__ import annotations

import os
import subprocess
import signal
from pathlib import Path
from typing import Any

import db

IGNORED = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def _safe_root(root: str) -> Path:
    p = Path(root).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Workspace directory does not exist: {p}")
    return p


def set_root(root: str) -> dict[str, Any]:
    p = _safe_root(root)
    db.set_setting("workspace_root", str(p))
    return status()


def _detect_default_root() -> Path | None:
    """Use the repo root when no explicit workspace is configured."""
    candidates: list[Path] = []
    current = Path.cwd().resolve()
    while True:
        candidates.append(current)
        if (current / "backend").exists() and (current / "frontend").exists() and (current / "README.md").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    for candidate in candidates:
        if (candidate / "backend").exists() and (candidate / "frontend").exists() and (candidate / "README.md").exists():
            return candidate
    return None


def root() -> Path | None:
    value = db.get_setting("workspace_root", "")
    if value:
        p = Path(value).expanduser().resolve()
        if p.exists() and p.is_dir():
            repo_root = _detect_default_root()
            if repo_root is not None and p != repo_root:
                # Keep the app anchored to the project root rather than stale temp/test paths.
                db.set_setting("workspace_root", str(repo_root))
                return repo_root
            return p
    detected = _detect_default_root()
    if detected is not None:
        db.set_setting("workspace_root", str(detected))
    return detected


def _run(args: list[str], timeout: int = 30) -> dict[str, Any]:
    p = root()
    if p is None:
        return {"ok": False, "error": "No workspace configured"}
    try:
        r = subprocess.run(args, cwd=str(p), capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "exit_code": r.returncode, "stdout": r.stdout[-12000:], "stderr": r.stderr[-12000:]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def status() -> dict[str, Any]:
    p = root()
    if p is None:
        return {"configured": False, "root": None, "git": False}
    git = _run(["git", "status", "--short", "--branch"])
    branch = _run(["git", "branch", "--show-current"])
    head = _run(["git", "rev-parse", "HEAD"])
    remote = _run(["git", "remote", "get-url", "origin"])
    return {
        "configured": True,
        "root": str(p),
        "git": git.get("ok", False),
        "branch": (branch.get("stdout") or "").strip(),
        "head": (head.get("stdout") or "").strip(),
        "remote": (remote.get("stdout") or "").strip(),
        "status": git,
    }


def _safe_target(rel: str, *, allow_missing: bool = True) -> Path:
    p = root()
    if p is None: raise ValueError("No workspace configured")
    from security import safe_path
    try:
        return safe_path(p, rel, allow_missing=allow_missing)
    except PermissionError as exc:
        raise ValueError(str(exc)) from exc

def write_file(path: str, content: str) -> dict[str, Any]:
    target = _safe_target(path, allow_missing=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(target.relative_to(root())).replace("\\\\", "/")}


def read_file(path: str) -> str:
    target = _safe_target(path, allow_missing=False)
    return target.read_text(encoding="utf-8")


def git(args: list[str], timeout: int = 60) -> dict[str, Any]:
    return _run(["git", *args], timeout=timeout)

def run_shell(command: str, timeout: int = 120) -> dict[str, Any]:
    """Run a user-requested project command in the canonical workspace.

    The command is intentionally executed by the platform shell because generated
    projects commonly need compound commands (cd, &&, npm scripts, cmake, etc.).
    Callers must only pass commands derived from a trusted project/build plan.
    """
    p = root()
    if p is None:
        return {"ok": False, "error": "No workspace configured"}
    if not command.strip():
        return {"ok": False, "error": "Empty command"}
    shell = os.environ.get("COMSPEC") if os.name == "nt" else "/bin/sh"
    args = [shell, "/c", command] if os.name == "nt" else [shell, "-lc", command]
    try:
        r = subprocess.run(args, cwd=str(p), capture_output=True, text=True, timeout=timeout)
        return {
            "ok": r.returncode == 0,
            "exit_code": r.returncode,
            "stdout": r.stdout[-12000:],
            "stderr": r.stderr[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": f"Command timed out after {timeout}s", "stdout": (exc.stdout or "")[-12000:] if exc.stdout else "", "stderr": (exc.stderr or "")[-12000:] if exc.stderr else ""}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def project_commands() -> list[str]:
    return db.get_setting("project_commands", []) or []


def run_project_command(name_or_command: str, timeout: int = 120) -> dict[str, Any]:
    commands = project_commands()
    command = name_or_command
    aliases = {"test": 0, "build": 1, "dev": 2, "lint": 3, "format": 4}
    if name_or_command in aliases and aliases[name_or_command] < len(commands):
        command = commands[aliases[name_or_command]]
    if not command:
        return {"ok": False, "error": "No project command configured"}
    return _run(["sh", "-lc", command], timeout=timeout)


def create_checkpoint(reason: str = "manual") -> dict[str, Any]:
    p = root()
    if p is None: return {"ok": False, "error": "No workspace configured"}
    from checkpoints import create
    return create(p, reason)

def list_checkpoints() -> list[dict[str, Any]]:
    p = root()
    if p is None: return []
    from checkpoints import list_checkpoints as _list
    return _list(p)

def restore_checkpoint(path: str, dry_run: bool = False) -> dict[str, Any]:
    p = root()
    if p is None: return {"ok": False, "error": "No workspace configured"}
    from checkpoints import restore
    return restore(p, path, dry_run=dry_run)
