"""Container sandbox for autonomous build/test execution.

The sandbox is deliberately fail-closed: if a container runtime is unavailable,
callers receive an explicit failure instead of silently executing on the host.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def engine():
    return shutil.which("docker") or shutil.which("podman")


def available():
    return bool(engine())


def _image(command):
    if "npm " in command or "node " in command:
        return os.getenv("DREAMCODER_SANDBOX_NODE_IMAGE", "node:22-bookworm-slim")
    if "cargo " in command or "rustc " in command:
        return os.getenv("DREAMCODER_SANDBOX_RUST_IMAGE", "rust:1.89-slim")
    if "go " in command:
        return os.getenv("DREAMCODER_SANDBOX_GO_IMAGE", "golang:1.25-bookworm")
    if "dotnet " in command:
        return os.getenv("DREAMCODER_SANDBOX_DOTNET_IMAGE", "mcr.microsoft.com/dotnet/sdk:9.0")
    if "mvn " in command or "java " in command:
        return os.getenv("DREAMCODER_SANDBOX_JAVA_IMAGE", "maven:3.9-eclipse-temurin-21")
    return os.getenv("DREAMCODER_SANDBOX_IMAGE", "python:3.12-slim")


def run(root: str, command: str, timeout: int = 300, network: bool = False):
    runtime = engine()
    if not runtime:
        return {
            "ok": False,
            "exit_code": -1,
            "error": "No Docker/Podman sandbox runtime installed",
            "sandboxed": False,
        }

    workspace_root = Path(root).resolve()
    if not workspace_root.is_dir():
        return {"ok": False, "exit_code": -1, "error": "sandbox root does not exist", "sandboxed": False}
    if not command.strip():
        return {"ok": False, "exit_code": -1, "error": "empty sandbox command", "sandboxed": False}

    image = _image(command)
    args = [
        runtime, "run", "--rm",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "128",
        "--memory", "2g",
        "--cpus", "2",
        "--user", "65532:65532",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m",
        "--mount", f"type=bind,src={workspace_root},dst=/workspace,rw",
        "--workdir", "/workspace",
        "--network", "bridge" if network else "none",
        image, "sh", "-lc", command,
    ]
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=max(5, min(timeout, 900)),
        )
        return {
            "ok": p.returncode == 0,
            "exit_code": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
            "sandboxed": True,
            "engine": Path(runtime).name,
            "image": image,
            "network": bool(network),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "sandbox timeout",
            "sandboxed": True,
            "timeout": True,
        }
