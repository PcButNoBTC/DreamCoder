from __future__ import annotations

import difflib
import os
import subprocess
import time
import db
from pathlib import Path
from typing import Any

from .permissions import PermissionError, command_allowed, workspace_path

class ToolRegistry:
    def __init__(self, root: str, timeout: int = 60, auto_apply: bool = False):
        self.root = str(Path(root).expanduser().resolve())
        self.timeout = min(max(timeout, 1), 300)
        self.auto_apply = auto_apply

    def _path(self, path: str) -> Path:
        return workspace_path(self.root, path)

    def read_file(self, path: str) -> dict[str, Any]:
        p = self._path(path)
        return {"path": str(p.relative_to(self.root)), "content": p.read_text(encoding="utf-8"), "size": p.stat().st_size}

    def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        q = query.lower()
        hits=[]
        ignored={".git","node_modules","__pycache__",".venv","venv","dist","build"}
        for p in Path(self.root).rglob("*"):
            if len(hits) >= limit or not p.is_file() or any(x in p.parts for x in ignored):
                continue
            try:
                text=p.read_text(encoding="utf-8")
            except (UnicodeDecodeError,OSError):
                continue
            for i,line in enumerate(text.splitlines(),1):
                if q in line.lower():
                    hits.append({"path":str(p.relative_to(self.root)),"line":i,"text":line[:500]})
                    if len(hits)>=limit: break
        return {"query":query,"hits":hits}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        if not self.auto_apply: raise PermissionError("write_file requires approval")
        p=self._path(path); p.parent.mkdir(parents=True,exist_ok=True); before=p.read_text(encoding="utf-8") if p.exists() else ""
        p.write_text(content,encoding="utf-8")
        return {"path":str(p.relative_to(self.root)),"created":not bool(before),"change_type":"APP_MODIFY","diff":"".join(difflib.unified_diff(before.splitlines(True),content.splitlines(True),fromfile=str(p),tofile=str(p)))}

    def apply_patch(self, path: str, old: str, new: str) -> dict[str, Any]:
        if not self.auto_apply: raise PermissionError("apply_patch requires approval")
        p=self._path(path)
        current=p.read_text(encoding="utf-8")
        if old not in current: raise ValueError(f"Patch anchor not found in {path}")
        updated=current.replace(old,new,1)
        p.write_text(updated,encoding="utf-8")
        return {"path":path,"change_type":"APP_MODIFY","diff":"".join(difflib.unified_diff(current.splitlines(True),updated.splitlines(True),fromfile=path,tofile=path))}

    def run(self, command: str) -> dict[str, Any]:
        from .permissions import split_segments, unrestricted_mode
        segments = split_segments(command)
        started = time.perf_counter()
        outputs = []
        overall_ok = True
        if unrestricted_mode():
            argv, _ = segments[0]
            p = subprocess.run(argv, cwd=self.root, shell=True, capture_output=True, text=True,
                               timeout=self.timeout, env=os.environ.copy())
            outputs.append({"command": argv, "exit_code": p.returncode,
                            "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]})
            overall_ok = p.returncode == 0
        else:
            short_circuit = False
            for argv, op in segments:
                if short_circuit:
                    outputs.append({"command": " ".join(argv), "skipped": True})
                    continue
                p = subprocess.run(argv, cwd=self.root, shell=False, capture_output=True, text=True,
                                   timeout=self.timeout, env=os.environ.copy())
                outputs.append({"command": " ".join(argv), "exit_code": p.returncode,
                                "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]})
                if op == "and" and p.returncode != 0:
                    overall_ok = False
                    short_circuit = True
                elif op == "or" and p.returncode == 0:
                    short_circuit = True
        latency = int((time.perf_counter() - started) * 1000)
        try:
            from backup_manager import log_command
            log_command(command, self.root, 0 if overall_ok else 1)
        except Exception:
            pass
        return {"ok": overall_ok, "command": command, "segments": outputs,
                "latency_ms": latency, "unrestricted": unrestricted_mode()}

    def test(self, command: str = "") -> dict[str, Any]:
        configured = db.get_setting("project_commands", []) or []
        if not command and configured:
            command = configured[0]
        return self.run(command or "pytest -q")

    def git_status(self) -> dict[str, Any]:
        return self.run("git status --short --branch")

    def git_diff(self) -> dict[str, Any]:
        return self.run("git diff --")

    def dispatch(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        fn=getattr(self,tool,None)
        if not fn: raise ValueError(f"Unknown tool: {tool}")
        return fn(**args)
