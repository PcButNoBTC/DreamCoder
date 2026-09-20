"""Workspace security, capability policy, secret redaction and path hardening."""
from __future__ import annotations
import os,re,stat
from pathlib import Path
from typing import Any
SAFE_COMMANDS={"git","python","python3","pytest","node","npm","npx","pnpm","yarn","cargo","rustc","go","java","javac","mvn","dotnet","cmake","make","bash","sh","cmd","powershell"}
SECRET_PATTERNS=[
 re.compile(r"(ghp_[A-Za-z0-9_]+)",re.I), re.compile(r"(github_pat_[A-Za-z0-9_]+)",re.I),
 re.compile(r"(hf_[A-Za-z0-9_]+)",re.I), re.compile(r"(sk-[A-Za-z0-9_-]{16,})",re.I),
 re.compile(r"(Bearer\s+)[A-Za-z0-9._-]+",re.I),
 re.compile(r"((?:token|api[_-]?key|password|secret)\s*[=:]\s*)[^\s,;]+",re.I),
 re.compile(r"(AKIA[0-9A-Z]{16})"),
 re.compile(r"(-----BEGIN [A-Z ]+ PRIVATE KEY-----).*?(-----END [A-Z ]+ PRIVATE KEY-----)", re.I | re.S)]
def redact(text:str)->str:
    out=text or ""
    for p in SECRET_PATTERNS: out=p.sub(lambda m: (m.group(1) if m.lastindex else "")+"[REDACTED]",out)
    return out
def safe_path(root:str|Path, relative:str, allow_missing=True)->Path:
    base=Path(root).expanduser().resolve(); rel=Path(relative)
    raw=str(relative).replace("\\\\","/")
    if re.match(r"^[A-Za-z]:/",raw) or raw.startswith("/") or raw.startswith("//") or rel.is_absolute() or ".." in rel.parts: raise PermissionError("path escapes workspace")
    target=(base/rel).resolve(strict=not allow_missing)
    if target!=base and base not in target.parents: raise PermissionError("path escapes workspace")
    if target.is_symlink() or any(part.is_symlink() for part in [base.joinpath(*rel.parts[:i]) for i in range(1,len(rel.parts)+1)] if part.exists()): raise PermissionError("symlink targets are not allowed")
    return target
def capabilities()->dict[str,bool]:
    return {"read_workspace":True,"write_workspace":True,"execute":os.getenv("DREAMCODER_AGENT_UNRESTRICTED","0")=="1","network":os.getenv("DREAMCODER_AGENT_NETWORK","0")=="1","git":True,"github":bool(os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"))}
def audit_store_status() -> dict[str, Any]:
    """Report whether the audit log is owner-readable only."""
    from pathlib import Path
    p = Path(os.getenv("DREAMCODER_AUDIT_LOG", "~/.dreamcoder/audit.jsonl")).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.touch(mode=0o600, exist_ok=True)
        else:
            p.chmod(stat.S_IRUSR | stat.S_IWUSR)
        mode = stat.S_IMODE(p.stat().st_mode)
        return {"ok": bool(p.is_file() and not (mode & 0o077)), "path": str(p), "mode": oct(mode)}
    except Exception as exc:
        return {"ok": False, "path": str(p), "error": str(exc)}


def audit(event: str, **data: Any) -> None:
    from pathlib import Path
    import json, time
    p = Path(os.getenv("DREAMCODER_AUDIT_LOG", "~/.dreamcoder/audit.jsonl")).expanduser()
    if not audit_store_status()["ok"]:
        return
    safe = {k: redact(str(v)) for k, v in data.items()}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "event": event, **safe}) + "\n")


def command_capability(command: str, unrestricted: bool = False) -> dict[str, Any]:
    exe = (command.strip().split()[0] if command.strip() else "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    allowed = unrestricted or exe in SAFE_COMMANDS
    return {"allowed": allowed, "executable": exe, "reason": "" if allowed else "executable is not allowlisted"}
