"""Canonical project workspace and Git runtime for DreamCoder."""

from __future__ import annotations

import os
import subprocess
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


def root() -> Path | None:
    value = db.get_setting("workspace_root", "")
    if not value:
        return None
    p = Path(value).expanduser().resolve()
    return p if p.exists() and p.is_dir() else None


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


def write_file(path: str, content: str) -> dict[str, Any]:
    p = root()
    if p is None:
        raise ValueError("No workspace configured")
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Invalid workspace path")
    target = (p / rel).resolve()
    if p not in target.parents and target != p:
        raise ValueError("Path escapes workspace")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(target.relative_to(p)).replace("\\", "/")}


def read_file(path: str) -> str:
    p = root()
    if p is None:
        raise ValueError("No workspace configured")
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Invalid workspace path")
    target = (p / rel).resolve()
    if p not in target.parents:
        raise ValueError("Path escapes workspace")
    return target.read_text(encoding="utf-8")


def git(args: list[str], timeout: int = 60) -> dict[str, Any]:
    return _run(["git", *args], timeout=timeout)
