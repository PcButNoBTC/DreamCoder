"""Production control-plane: readiness, diagnostics and operational status."""
from __future__ import annotations

import os
import platform
import time
from pathlib import Path
from typing import Any

import db
from checkpoints import list_checkpoints
from project_memory import memory
from sandbox import available as sandbox_available
from security import audit_store_status, capabilities


def init():
    db.init_db()
    db.set_setting("schema_version", max(int(db.get_setting("schema_version", 0) or 0), 2))
    return True


def _configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def readiness() -> dict[str, Any]:
    """Return operational readiness without treating optional integrations as core failures.

    The API can be healthy while GitHub, an AI provider, a workspace, or a container
    runtime is intentionally unconfigured. Those capabilities are reported separately
    as degraded/optional checks so desktop and local-only deployments remain usable.
    """
    root = db.get_setting("workspace_root", "")
    workspace_configured = bool(root and os.path.isdir(os.path.expanduser(str(root))))
    checks = {
        "database": bool(db.DB_PATH),
        "database_writable": _database_writable(),
        "audit_store": audit_store_status()["ok"],
        "workspace": workspace_configured,
        "github_config": bool(
            _configured("GITHUB_TOKEN")
            or _configured("GH_TOKEN")
            or _configured("GITHUB_APP_TOKEN")
            or db.get_setting("github_oauth_token", "")
        ),
        "ai_config": bool(
            _configured("HF_TOKEN")
            or _configured("OLLAMA_BASE_URL")
            or _configured("DREAMCODER_OLLAMA_PRIMARY_URL")
            or _configured("OPENAI_API_KEY")
        ),
        "checkpoint_store": True,
        "sandbox": sandbox_available(),
    }

    required = ("database", "database_writable", "audit_store", "checkpoint_store")
    optional = ("workspace", "github_config", "ai_config", "sandbox")
    return {
        "ok": all(checks[name] for name in required),
        "checks": checks,
        "required_checks": list(required),
        "optional_checks": list(optional),
        "degraded": [name for name in optional if not checks[name]],
        "platform": platform.platform(),
        "python": platform.python_version(),
        "schema_version": db.get_setting("schema_version", 1),
        "capabilities": capabilities(),
        "time": time.time(),
    }


def _database_writable() -> bool:
    try:
        conn = db.get_conn()
        conn.execute("SELECT 1")
        conn.close()
        return True
    except Exception:
        return False


def diagnostics(root: str | None = None) -> dict[str, Any]:
    return {
        "readiness": readiness(),
        "db": {"path": str(db.DB_PATH), "stats": db.symbol_stats()},
        "memory": memory.graph(100),
        "checkpoints": list_checkpoints(root),
        "audit": audit_store_status(),
        "env": {
            "autosync": os.getenv("DREAMCODER_GITHUB_AUTOSYNC", "true"),
            "agent_unrestricted": os.getenv("DREAMCODER_AGENT_UNRESTRICTED", "0"),
            "sandbox": os.getenv("DREAMCODER_SANDBOX_IMAGE", "python:3.12-slim"),
        },
    }
