from __future__ import annotations
import os,re,shlex
from pathlib import Path

SAFE_COMMANDS={"python","python3","pytest","pip","pip3","git","npm","npx","node","yarn","pnpm","uv","ruff","mypy","pyright","go","cargo","rustc","cmake","make","gcc","g++","clang","dotnet","java","javac","mvn","gradle","ls","cat","echo","pwd","which","where","dir","type","find","grep","rg","head","tail","wc","sort","uniq","diff"}
FORBIDDEN_CHARS=set(";$"+chr(96)+"><\\\n\r")

class PermissionError(RuntimeError): pass

def unrestricted_mode()->bool:
    return os.getenv("DREAMCODER_AGENT_UNRESTRICTED","0").lower() in {"1","true","yes","on"}

def workspace_path(root:str,path:str)->Path:
    base=Path(root).expanduser().resolve()
    candidate=(base/path).resolve() if not Path(path).is_absolute() else Path(path).expanduser().resolve()
    if candidate!=base and base not in candidate.parents: raise PermissionError(f"Path escapes workspace: {path}")
    return candidate

def split_segments(command:str):
    cmd=command.strip()
    if not cmd: raise PermissionError("Empty command")
    if unrestricted_mode(): return [(cmd,"and")]
    for ch in FORBIDDEN_CHARS:
        if ch in cmd: raise PermissionError(f"Command contains forbidden character: {ch!r}")
    segments=[]; current_op="and"
    for part in re.split(r"(&&|\|\|)",cmd):
        part=part.strip()
        if part in ("&&","||"):
            current_op="and" if part=="&&" else "or"; continue
        if not part: continue
        try: argv=shlex.split(part)
        except ValueError as exc: raise PermissionError(f"Cannot parse command segment: {exc}") from exc
        if not argv: continue
        executable=Path(argv[0]).name.lower()
        if executable not in SAFE_COMMANDS: raise PermissionError(f"Executable not in allowlist: {executable}")
        segments.append((argv,current_op))
    if not segments: raise PermissionError("No runnable segments")
    return segments

def command_allowed(command:str)->bool:
    try: split_segments(command); return True
    except PermissionError: return False

def require_write_approval(auto_apply:bool)->None:
    if not auto_apply: raise PermissionError("Write operations require explicit approval")
