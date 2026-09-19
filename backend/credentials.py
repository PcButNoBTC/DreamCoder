"""OS credential storage abstraction. Uses keyring when installed; never returns secrets to the UI."""
from __future__ import annotations
import os
from typing import Any

try:
    import keyring
except Exception:
    keyring = None

SERVICE = "DreamCoder"


def _keyring_ready() -> bool:
    if keyring is None:
        return False
    try:
        backend = keyring.get_keyring()
        module = getattr(backend, "__class__", type(backend)).__module__ or ""
        return "keyring.backends.fail" not in module
    except Exception:
        return False


def available() -> bool:
    return _keyring_ready()


def set_secret(name: str, value: str) -> dict[str, Any]:
    if not name or "/" in name:
        return {"ok": False, "error": "invalid credential name"}
    if not _keyring_ready():
        return {"ok": False, "error": "keyring backend is not configured"}
    keyring.set_password(SERVICE, name, value)
    return {"ok": True, "name": name, "stored": True}


def get_secret(name: str) -> str:
    if not _keyring_ready():
        return ""
    try:
        return keyring.get_password(SERVICE, name) or ""
    except Exception:
        return ""


def has_secret(name: str) -> bool:
    if not _keyring_ready():
        return False
    try:
        return bool(keyring.get_password(SERVICE, name))
    except Exception:
        return False


def delete_secret(name: str) -> dict[str, Any]:
    if not _keyring_ready():
        return {"ok": False, "error": "keyring backend is not configured"}
    try:
        keyring.delete_password(SERVICE, name)
    except Exception:
        pass
    return {"ok": True, "name": name}


def status() -> dict[str, Any]:
    ready = available()
    return {
        "available": ready,
        "github_token": has_secret("github_token") if ready else False,
        "hf_token": has_secret("hf_token") if ready else False,
    }
