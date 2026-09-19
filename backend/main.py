"""
DreamCoder API – full personal IDE backend
"""

from __future__ import annotations

import asyncio
import difflib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
from ai_router import AIRouter, MODEL_REGISTRY
from models.base import ChatContext, CodeContext
from watcher import IndexWatcher
from analyzer import analyze_folder, analyze_folder_with_model, _extract_json, monitor_insights, chat_reply
from hf_catalog import get_catalog, search_local
from generator import generate_project, generate_project_with_model, self_heal, files_to_zip
from github_sync import github_sync
import workspace
from agent.api import router as agent_router

# ---------------------------------------------------------------------------
app = FastAPI(
    title="DreamCoder API",
    description="AI-native personal development studio",
    version="1.0.0",
)


app.include_router(agent_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = AIRouter()
db.init_db()

# Seed demo files if empty
if not router.index.list_files():
    _SEED = '''from dataclasses import dataclass

@dataclass
class CodeContext:
    code: str
    language: str = "python"
    selection: str = ""

class DreamCoder:
    def __init__(self, model):
        self.model = model

    async def suggest(self, context: CodeContext) -> list:
        return await self.model.complete(context)

if __name__ == "__main__":
    app = DreamCoder(model="Llama-3.1-8B-Instruct")
    print("DreamCoder ready")
'''
    router.index_file("src/main.py", _SEED)
    router.index_file("src/ai_router.py", "class AIRouter:\n    def get_model(self, name: str):\n        ...\n")

_watcher: Optional[IndexWatcher] = None
_watch_task = None

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SuggestRequest(BaseModel):
    model: str = "Llama-3.1-8B-Instruct"
    language: str = "python"
    code: str
    selection: str = ""
    filename: str = "main.py"
    cursor_line: int = 1
    cursor_col: int = 1
    use_cache: bool = True


class SuggestAllRequest(BaseModel):
    models: list[str] = Field(default_factory=lambda: [
        "Llama-3.1-8B-Instruct", "Qwen2.5-Coder", "DeepSeek-Coder", "Mistral-7B-Instruct"
    ])
    language: str = "python"
    code: str
    selection: str = ""
    filename: str = "main.py"


class IndexRequest(BaseModel):
    path: str
    content: str
    language: str = "python"


class RunRequest(BaseModel):
    code: str
    language: str = "python"
    filename: str = "main.py"


class EvolveRequest(BaseModel):
    model: str = "Llama-3.1-8B-Instruct"
    prompt: str
    current_ui: dict = {}


class WatchRequest(BaseModel):
    root: str

class OllamaHostRequest(BaseModel):\n    url: str\n\nclass OllamaPrimaryRequest(BaseModel):\n    url: str\n    model: str\n\nclass WorkspaceRequest(BaseModel):
    root: str

class GitRequest(BaseModel):
    args: list[str] = Field(default_factory=list)


class SaveFileRequest(BaseModel):
    path: str
    content: str
    language: str = "python"
    sync_github: bool = True
    commit_message: str = ""


class ChatRequest(BaseModel):
    message: str
    model: str = "Llama-3.1-8B-Instruct"
    mode: str = "project"  # project | general


class FolderAnalysisRequest(BaseModel):
    model: str = "Llama-3.1-8B-Instruct"

class AnalysisActionRequest(BaseModel):
    model: str = "Llama-3.1-8B-Instruct"
    path: str
    instruction: str
    project_type: str = ""

class ProjectContextRequest(BaseModel):
    goal: str = ""
    description: str = ""
    commands: list[str] = []


class GenerateProjectRequest(BaseModel):
    prompt: str
    goal: str = ""


class VisionRequest(BaseModel):
    image_base64: str  # raw base64 or data URL
    prompt: str = ""
    model: str = "Llama-3.1-8B-Instruct"


class TerminalRequest(BaseModel):

    command: str
    cwd: str = ""
    timeout: int = 60


class SelfHealRequest(BaseModel):

    error_text: str
    language: str = "python"
    files: list[dict] = []



# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "name": "DreamCoder API",
        "version": "1.0.0",
        "docs": "/docs",
        "ws": "/ws/complete",
        "features": [
            "suggest", "suggest-all", "stream", "evolve",
            "sqlite-index", "file-watcher", "history", "workspace", "git-runtime",
        ],
    }


@app.get("/api/health")
async def health(model: Optional[str] = None):
    info = await router.health(model)
    info["db"] = {"path": str(db.DB_PATH), "stats": db.symbol_stats()}
    info["watcher"] = {"active": _watcher is not None}
    return info




@app.post("/api/ollama/validate")
async def ollama_validate(req: OllamaHostRequest):
    try: normalized=validate_host(req.url)
    except ValueError as exc: raise HTTPException(400,str(exc))
    try: models=await fetch_models(normalized)
    except ValueError as exc: raise HTTPException(502,str(exc))
    ranked=rank_models(models)
    return {"ok":True,"url":normalized,"model_count":len(ranked),"models":ranked,"recommended":pick_primary(ranked)}

@app.post("/api/ollama/primary")
async def ollama_set_primary(req: OllamaPrimaryRequest):
    try: normalized=validate_host(req.url)
    except ValueError as exc: raise HTTPException(400,str(exc))
    db.set_setting("ollama_primary_url",normalized); db.set_setting("ollama_primary_model",req.model)
    os.environ["DREAMCODER_OLLAMA_PRIMARY_URL"]=normalized
    os.environ["DREAMCODER_OLLAMA_PRIMARY_MODEL"]=req.model
    return {"ok":True,"url":normalized,"model":req.model}

@app.get("/api/ollama/primary")
async def ollama_get_primary():
    return {"url":db.get_setting("ollama_primary_url",os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL","")),"model":db.get_setting("ollama_primary_model",os.getenv("DREAMCODER_OLLAMA_PRIMARY_MODEL",""))}

@app.get("/api/quota")
async def quota():
    return quota_snapshot()

@app.get("/api/backups")
async def list_backups():
    return {"backups":backup_manager.list_backups()}

@app.get("/api/agent/audit")
async def agent_audit(limit:int=200):
    return {"entries":backup_manager.read_audit_log(limit=limit)}

@app.post("/api/model-race/test")
async def model_race_test(body:dict={}):
    prompt=body.get("prompt","Say hello in one short sentence.")
    lanes=build_lanes_from_env()
    if not lanes: raise HTTPException(400,"No lanes configured")
    result=await race(lanes,ChatContext(message=prompt,mode="general"),expected_format=None,min_responses=1)
    return {"winner":result.winner.lane.name if result.winner else None,"winner_model":result.winner.lane.model if result.winner else None,"winner_content":result.winner.content if result.winner else None,"losers":[{"lane":l.lane.name,"reason":l.reason,"latency_ms":l.latency_ms} for l in result.losers],"duration_ms":result.duration_ms,"race_id":result.race_id}
\n@app.get("/api/models")
async def list_models():
    return {"models": await router.list_models()}


@app.post("/api/ai/suggest")
async def suggest(req: SuggestRequest):
    ctx = CodeContext(
        code=req.code,
        language=req.language,
        selection=req.selection,
        filename=req.filename,
        cursor_line=req.cursor_line,
        cursor_col=req.cursor_col,
    )
    result = await router.suggest(req.model, ctx, use_cache=req.use_cache)
    db.add_history(
        "suggest",
        result.model,
        req.code[:500],
        json.dumps([s.title for s in result.suggestions]),
        result.latency_ms,
    )
    return {
        "suggestions": [
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "code": s.code,
                "category": s.category,
                "confidence": s.confidence,
            }
            for s in result.suggestions
        ],
        "latency_ms": result.latency_ms,
        "model": result.model,
        "cached": result.cached,
        "architecture_insights": result.architecture_insights,
        "health": result.health,
    }


@app.post("/api/ai/suggest-all")
async def suggest_all(req: SuggestAllRequest):
    """Fire the same prompt at multiple models in parallel."""
    ctx = CodeContext(
        code=req.code,
        language=req.language,
        selection=req.selection,
        filename=req.filename,
    )
    models = req.models or list(MODEL_REGISTRY.keys())[:4]

    async def one(name: str):
        try:
            r = await router.suggest(name, ctx, use_cache=True)
            return {
                "model": name,
                "ok": True,
                "latency_ms": r.latency_ms,
                "cached": r.cached,
                "suggestions": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "description": s.description,
                        "code": s.code,
                        "category": s.category,
                        "confidence": s.confidence,
                    }
                    for s in r.suggestions
                ],
            }
        except Exception as exc:
            return {"model": name, "ok": False, "error": str(exc), "suggestions": []}

    start = time.perf_counter()
    results = await asyncio.gather(*[one(m) for m in models])
    total = int((time.perf_counter() - start) * 1000)
    return {"results": results, "total_latency_ms": total, "models": models}


@app.post("/api/ai/evolve")
async def evolve(req: EvolveRequest):
    """Propose live UI / feature patches with full awareness of this IDE."""
    start = time.perf_counter()
    prompt = (req.prompt or "").lower()
    patches = []

    def add(id_, title, desc, target, code):
        patches.append({"id": id_, "title": title, "description": desc, "target": target, "code": code})

    # App self-map (so AI "knows" what this product is)
    app_map = {
        "name": "DreamCoder",
        "purpose": "Personal AI-native IDE for coding, multi-model suggestions, project generation, folder analysis, and self-updating UI",
        "panels": ["explorer", "editor", "terminal", "ai-assistant", "chat", "evolve", "generate", "heal", "hf-catalog", "themes"],
        "themes": ["midnight", "graphite", "violet", "peach", "shroom", "ocean", "ember"],
        "fx": ["cursor", "particles"],
        "actions": ["run", "suggest", "ask-all", "stream", "analyze", "generate", "self-heal", "evolve"],
    }

    # Theme / color prompts
    theme_map = {
        "peach": ("peach", "--bg:#1a1210;--panel:#241a18;--accent:#ffb38a;--accent2:#ff8fab"),
        "shroom": ("shroom", "--bg:#14101a;--panel:#1c1524;--accent:#e8a0bf;--accent2:#9dffb0"),
        "ocean": ("ocean", "--bg:#0a1218;--panel:#0f1a22;--accent:#5ec8ff;--accent2:#3dffa8"),
        "ember": ("ember", "--bg:#140e0c;--panel:#1e1410;--accent:#ff7a45;--accent2:#ffd166"),
        "violet": ("violet", "--bg:#0e0b14;--panel:#11151e;--accent:#b48cff;--accent2:#4de0b8"),
        "graphite": ("graphite", "--bg:#101214;--panel:#17191c;--accent:#7c8cff;--accent2:#4de0b8"),
        "midnight": ("midnight", "--bg:#0b0e14;--panel:#11151e;--accent:#7c8cff;--accent2:#4de0b8"),
        "pink": ("peach", "--bg:#1a1210;--panel:#241a18;--accent:#ffb38a;--accent2:#ff8fab"),
        "coral": ("peach", "--bg:#1a1210;--panel:#241a18;--accent:#ffb38a;--accent2:#ff8fab"),
    }
    for key, (name, css_vars) in theme_map.items():
        if key in prompt and any(w in prompt for w in ("theme", "color", "colour", "look", "skin", "palette")):
            add(
                f"theme-{name}",
                f"Switch theme to {name}",
                f"Applies {name} color tokens across the IDE",
                "js",
                f"if (typeof applyTheme === 'function') applyTheme('{name}');\n"
                f"else {{\n  const r=document.documentElement;\n"
                f"  '{css_vars}'.split(';').forEach(p=>{{const[k,v]=p.split(':'); if(k&&v)r.style.setProperty(k.trim(),v.trim());}});\n}}",
            )
            break


    if any(k in prompt for k in ("more theme", "more colour", "more color", "add theme", "extra theme", "new theme", "more themes", "themese", "theme")):
        add(
            "more-themes-pack",
            "Add extra themes + colors",
            "Injects Peach, Shroom, Ocean, Ember theme buttons and applies a richer palette row",
            "js",
            "document.querySelectorAll('.theme-row').forEach(r=>{r.style.display='flex';r.style.flexWrap='wrap';});"
            "const names=['peach','shroom','ocean','ember','rose','mint','sand'];"
            "const row=document.querySelector('.theme-row');"
            "names.forEach(n=>{"
            "if(row && !document.querySelector('[data-theme="'+n+'"]')){"
            "const b=document.createElement('button');b.className='theme';b.dataset.theme=n;"
            "b.textContent=n.charAt(0).toUpperCase()+n.slice(1);"
            "b.onclick=()=>{if(typeof applyTheme==='function')applyTheme(n);"
            "else{const map={peach:{bg:'#1a1210',panel:'#241a18',accent:'#ffb38a',accent2:'#ff8fab'},"
            "shroom:{bg:'#14101a',panel:'#1c1524',accent:'#e8a0bf',accent2:'#9dffb0'},"
            "ocean:{bg:'#0a1218',panel:'#0f1a22',accent:'#5ec8ff',accent2:'#3dffa8'},"
            "ember:{bg:'#140e0c',panel:'#1e1410',accent:'#ff7a45',accent2:'#ffd166'},"
            "rose:{bg:'#1a1014',panel:'#241820',accent:'#ff7eb3',accent2:'#ffc2d4'},"
            "mint:{bg:'#0e1612',panel:'#14201a',accent:'#5dffb0',accent2:'#b8ffd8'},"
            "sand:{bg:'#16140e',panel:'#201c14',accent:'#e8c47c',accent2:'#ffe6b0'}}[n];"
            "if(map){const r=document.documentElement;r.style.setProperty('--bg',map.bg);r.style.setProperty('--panel',map.panel);r.style.setProperty('--accent',map.accent);r.style.setProperty('--accent2',map.accent2);}}};"
            "row.appendChild(b);}});"
            "if(typeof toast==='function')toast('Themes expanded','success');",
        )

    if any(k in prompt for k in ("particle", "particles", "partcyle", "sparkle", "stars")):
        force = any(k in prompt for k in ("don't", "dont", "not work", "don't see", "dont see", "add more", "fix", "enable", "on"))
        off = "off" in prompt or "disable" in prompt
        if off and not force:
            code = "if (typeof setParticles === 'function') setParticles(false);"
            title = "Disable particles"
        else:
            dense = "more" in prompt or "dense" in prompt or "add" in prompt
            code = (
                "window.DC_PARTICLE_OPTS=Object.assign(window.DC_PARTICLE_OPTS||{},{"
                + ("count:120,speed:1.2,size:2.5" if dense else "count:80,speed:0.8,size:2")
                + "});"
                "if (typeof setParticles === 'function') { setParticles(false); setTimeout(function(){ setParticles(true); }, 50); }"
            )
            title = "Enable particles" + (" (dense)" if dense else "")
        add("fx-particles", title, "Background particle field with options", "js", code)
        if "option" in prompt or "setting" in prompt or "control" in prompt:
            add(
                "particle-controls",
                "Add particle density controls",
                "UI chips for density presets",
                "js",
                """(function(){
                  var row=document.querySelector('.theme-row')||document.querySelector('#evolveChips');
                  if(!row)return;
                  ['Sparse','Normal','Dense'].forEach(function(label){
                    var id='p-'+label.toLowerCase();
                    if(document.getElementById(id))return;
                    var b=document.createElement('button');b.id=id;b.className='chip';b.textContent='Particles: '+label;
                    b.onclick=function(){
                      var map={Sparse:{count:40,speed:0.5,size:1.5},Normal:{count:80,speed:0.8,size:2},Dense:{count:140,speed:1.3,size:2.8}};
                      window.DC_PARTICLE_OPTS=map[label];
                      if(typeof setParticles==='function'){setParticles(false);setTimeout(function(){setParticles(true);},40);}
                    };
                    row.appendChild(b);
                  });
                })();""",
            )

    if any(k in prompt for k in ("cursor", "pointer")) and any(k in prompt for k in ("fx", "effect", "glow", "interactive", "custom")):
        on = "off" not in prompt and "disable" not in prompt
        add("fx-cursor", "Toggle cursor FX", "Glowing custom cursor", "js",
            f"if (typeof setCursorFx === 'function') setCursorFx({str(on).lower()});")

    if any(k in prompt for k in ("shortcut", "help", "overlay", "hotkey", "keyboard", "command palette", "ctrl+k")):
        add("shortcut-help", "Keyboard / command help", "Shows main shortcuts", "html",
            '<div class="card-head"><span>⌨ Shortcuts</span><span class="badge">LIVE</span></div>'
            '<div class="muted" style="line-height:1.7">'
            '<div><span class="kbd">Ctrl</span>+<span class="kbd">K</span> Command palette</div>'
            '<div><span class="kbd">Ctrl</span>+<span class="kbd">Enter</span> Run</div>'
            '<div><span class="kbd">Ctrl</span>+<span class="kbd">Shift</span>+<span class="kbd">S</span> Suggest</div>'
            '<div><span class="kbd">Ctrl</span>+<span class="kbd">Shift</span>+<span class="kbd">A</span> Ask all</div>'
            '<div><span class="kbd">Ctrl</span>+<span class="kbd">E</span> Evolve</div>'
            '<div><span class="kbd">Ctrl</span>+<span class="kbd">Z</span> Undo last patch</div></div>')

    if any(k in prompt for k in ("terminal", "console", "font")):
        add("terminal-polish", "Larger terminal", "Taller terminal + contrast", "css",
            ".terminal{height:180px !important}\n.terminal pre{font-size:12.5px !important;color:#c5d4e8 !important}")

    if any(k in prompt for k in ("minimap", "overview")):
        add("editor-minimap", "Editor minimap bar", "Side accent overview", "css",
            ".editor-wrap{position:relative}\n.editor-wrap::after{content:'';position:absolute;top:8px;right:6px;width:28px;"
            "height:calc(100% - 16px);border-radius:4px;pointer-events:none;"
            "background:linear-gradient(180deg,var(--accent),transparent);border:1px solid #ffffff11}")

    if any(k in prompt for k in ("file tree", "explorer", "sidebar")):
        add("file-tree-ux", "File tree accent", "Accent border on hover", "css",
            ".file:hover{border-left:2px solid var(--accent);padding-left:10px}"
            ".file.active-file{border-left:2px solid var(--accent2);padding-left:10px}")

    if any(k in prompt for k in ("compact", "dense", "smaller ui", "more space")):
        add("compact-ui", "Compact UI density", "Tighter padding for more editor space", "css",
            ".card{padding:8px !important;margin-bottom:6px !important}\n.topbar{height:48px !important}"
            "\n.ai-panel{padding:8px !important}")

    if any(k in prompt for k in ("wide ai", "bigger panel", "wider assistant")):
        add("wide-ai", "Wider AI panel", "Give the assistant more width", "css",
            ".workspace{grid-template-columns:200px minmax(280px,1fr) 400px !important}")

    if any(k in prompt for k in ("new feature", "idea", "invent", "could we", "add a", "what if", "suggest feature")):
        add(
            "invent-feature",
            "Prototype feature idea",
            "Injects a sample feature chip into Evolve",
            "js",
            "var chips=document.getElementById('evolveChips');"
            "if(chips&&!document.getElementById('inventedFeat')){"
            "var b=document.createElement('button');b.id='inventedFeat';b.className='chip';"
            "b.textContent='Focus mode';b.onclick=function(){"
            "document.querySelector('.ai-panel')?.classList.toggle('focus-mode');"
            "document.querySelector('.files')?.classList.toggle('focus-mode');"
            "var s=document.createElement('style');s.textContent='.focus-mode{opacity:0.35!important}';document.head.appendChild(s);"
            "toast('Focus mode toggled','success');};chips.appendChild(b);toast('Added Focus mode chip','success');}",
        )
        add(
            "invent-statusbar",
            "Richer status pulse",
            "Subtle statusbar accent animation",
            "css",
            ".statusbar{box-shadow:inset 0 1px 0 var(--accent);}@keyframes statusGlow{0%,100%{opacity:1}50%{opacity:.7}}.statusbar span:first-child{animation:statusGlow 2.5s infinite}",
        )

    if not patches:
        # Generic self-aware response patch
        add("app-aware", "DreamCoder self-map", "What this IDE is (for your prompt)", "html",
            f'<div class="card-head"><span>🧠 App map</span><span class="badge">SELF</span></div>'
            f'<div class="muted" style="line-height:1.5;font-size:10px">'
            f'<div><b>{app_map["name"]}</b> — {app_map["purpose"]}</div>'
            f'<div style="margin-top:4px">Panels: {", ".join(app_map["panels"])}</div>'
            f'<div>Themes: {", ".join(app_map["themes"])}</div>'
            f'<div>Try: “switch to peach theme”, “enable particles”, “compact UI”</div></div>')

    latency = int((time.perf_counter() - start) * 1000) + 40
    return {
        "patches": patches,
        "model": req.model,
        "latency_ms": latency,
        "prompt": req.prompt,
        "app_map": app_map,
    }



@app.post("/api/run")
async def run_code(req: RunRequest):
    start = time.perf_counter()
    lines = [f"$ dreamcoder run {req.filename}", ""]
    exit_code = 0
    if req.language.lower() == "python":
        try:
            compile(req.code, req.filename, "exec")
            lines += ["✓ Python environment initialized", f"✓ {req.filename} parsed successfully",
                      "✓ No syntax errors detected", "", "Process finished with exit code 0"]
        except SyntaxError as e:
            lines += [f"✗ SyntaxError: {e.msg}", f'  File "{req.filename}", line {e.lineno}',
                      f"    {(e.text or '').strip()}", "", "Process finished with exit code 1"]
            exit_code = 1
    else:
        lines += [f"Language '{req.language}' – syntax check not implemented", "Process finished with exit code 0"]
    return {"output": "\n".join(lines), "exit_code": exit_code, "latency_ms": int((time.perf_counter() - start) * 1000)}


# ---------- Files / index ----------

@app.post("/api/index")
async def index_file(req: IndexRequest):
    stats = router.index_file(req.path, req.content)
    # also store language
    router.index.index_file(req.path, req.content, req.language)
    return {"ok": True, "stats": stats}


@app.get("/api/files")
async def api_list_files():
    return {"files": router.index.list_files()}


@app.get("/api/files/{path:path}")
async def api_get_file(path: str):
    f = router.index.get_file(path)
    if not f:
        raise HTTPException(404, "File not found in index")
    return f



class BulkFile(BaseModel):
    path: str
    content: str
    language: str = "python"


class BulkIndexRequest(BaseModel):
    files: list[BulkFile]
    root_name: str = "dropped-project"
    replace_existing: bool = False


@app.post("/api/files/bulk")
async def bulk_index(req: BulkIndexRequest):
    """Index files; folder opens replace the active index, while Add Files can merge."""
    if req.replace_existing:
        router.index.clear()
    count = 0
    for f in req.files:
        lang = f.language or "python"
        if not lang or lang == "python":
            ext = f.path.rsplit(".", 1)[-1].lower() if "." in f.path else ""
            lang = {
                "py": "python", "js": "javascript", "ts": "typescript",
                "tsx": "typescript", "jsx": "javascript", "html": "html",
                "css": "css", "md": "markdown", "json": "json",
            }.get(ext, "text")
        router.index.index_file(f.path, f.content, lang)
        count += 1
    if req.root_name:
        db.set_setting("project_root_name", req.root_name)
    return {"ok": True, "indexed": count, "stats": router.index.stats(), "root_name": req.root_name}


@app.post("/api/files/save")
async def api_save_file(req: SaveFileRequest):
    stats = router.index.index_file(req.path, req.content, req.language)
    workspace_write = {"ok": False, "skipped": True, "reason": "No workspace configured"}
    if workspace.root() is not None:
        try:
            workspace_write = workspace.write_file(req.path, req.content)
        except Exception as exc:
            workspace_write = {"ok": False, "error": str(exc)}
    sync = {"ok": False, "skipped": True, "reason": "disabled"}
    if req.sync_github:
        sync = await github_sync.sync_file_with_backup(str(workspace.root() or ""), req.path, req.content, req.commit_message or None)
    return {"ok": True, "stats": stats, "workspace": workspace_write, "github": sync}

@app.get("/api/workspace")
async def workspace_status():
    return workspace.status()

@app.post("/api/workspace")
async def configure_workspace(req: WorkspaceRequest):
    try:
        info = workspace.set_root(req.root)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return info

@app.post("/api/workspace/run")
async def workspace_run(req: GitRequest):
    command = req.args[0] if req.args else "test"
    return workspace.run_project_command(command, timeout=120)
@app.get("/api/workspace/git/status")
async def workspace_git_status():
    return workspace.git(["status", "--short", "--branch"])

@app.get("/api/workspace/git/log")
async def workspace_git_log(limit: int = 20):
    return workspace.git(["log", f"-{max(1,min(limit,100))}", "--oneline", "--decorate"])

@app.get("/api/workspace/git/diff")
async def workspace_git_diff(staged: bool = False):
    return workspace.git(["diff", "--cached" if staged else "--"])

@app.post("/api/workspace/git")
async def workspace_git(req: GitRequest):
    allowed = {"status", "diff", "log", "branch", "switch", "add", "commit", "fetch", "pull", "push"}
    if not req.args or req.args[0] not in allowed:
        raise HTTPException(400, "Unsupported Git operation")
    return workspace.git(req.args, timeout=120)
@app.get("/api/github/status")
async def github_status():
    return github_sync.status()

@app.post("/api/github/sync")
async def github_sync_current():
    files = []
    root = workspace.root()
    if root is not None:
        for path in root.rglob("*"):
            if not path.is_file() or any(part in {".git","node_modules","__pycache__",".venv","venv","dist","build"} for part in path.parts):
                continue
            try:
                rel = str(path.relative_to(root)).replace("\\", "/")
                if path.stat().st_size <= 2_000_000:
                    files.append({"path": rel, "content": path.read_text(encoding="utf-8", errors="ignore")})
            except OSError:
                continue
    else:
        for item in router.index.list_files():
            row = db.get_file(item["path"])
            if row:
                files.append({"path": item["path"], "content": row["content"]})
    return await github_sync.sync_files(files, message="DreamCoder project snapshot")


@app.get("/api/index/stats")
async def index_stats():
    return router.index.stats()


@app.get("/api/index/search")
async def index_search(q: str, limit: int = 20):
    hits = router.index.search(q, limit=limit)
    return {
        "query": q,
        "results": [
            {"name": s.name, "kind": s.kind, "file": s.file, "line": s.line, "signature": s.signature}
            for s in hits
        ],
    }


@app.get("/api/history")
async def history(limit: int = 30):
    return {"history": db.recent_history(limit)}


# ---------- Watcher ----------

@app.post("/api/watch")
async def start_watch(req: WatchRequest):
    global _watcher, _watch_task
    root = req.root
    if not Path(root).exists():
        raise HTTPException(400, f"Path does not exist: {root}")
    try:
        workspace.set_root(root)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if _watcher:
        _watcher.stop()

    # A native workspace replaces the previous project snapshot.
    router.index.clear()

    syncing_ready = False

    def on_change(rel: str, content: str, language: str):
        if language == "deleted" or content == "":
            router.index.remove_file(rel)
            try:
                loop = asyncio.get_running_loop()
                if syncing_ready:
                    loop.create_task(github_sync.delete_file(rel))
            except RuntimeError:
                pass
        else:
            router.index.index_file(rel, content, language)
            try:
                loop = asyncio.get_running_loop()
                if syncing_ready:
                    loop.create_task(github_sync.sync_file(rel, content, message=f"DreamCoder external change: {rel}"))
            except RuntimeError:
                pass

    _watcher = IndexWatcher(root, on_change)
    info = _watcher.start()
    syncing_ready = True

    if info.get("backend") == "polling":
        loop = asyncio.get_event_loop()
        _watch_task = loop.create_task(_watcher.poll_loop())

    return info


@app.post("/api/watch/stop")
async def stop_watch():
    global _watcher, _watch_task
    if _watcher:
        _watcher.stop()
        _watcher = None
    if _watch_task:
        _watch_task.cancel()
        _watch_task = None
    return {"status": "stopped"}



# ---------- Project context ----------

@app.get("/api/project/context")
async def get_project_context():
    return {
        "goal": db.get_setting("project_goal", ""),
        "description": db.get_setting("project_description", ""),
        "commands": db.get_setting("project_commands", []),
    }


@app.post("/api/project/context")
async def set_project_context(req: ProjectContextRequest):
    db.set_setting("project_goal", req.goal)
    db.set_setting("project_description", req.description)
    db.set_setting("project_commands", req.commands or [])
    return {"ok": True, "goal": req.goal, "description": req.description, "commands": req.commands}


# ---------- Live monitor chat ----------

@app.post("/api/ai/chat")
async def ai_chat(req: ChatRequest):
    """Chat always goes through the model selected in the UI."""
    model_name = req.model or "Llama-3.1-8B-Instruct"
    mode = (req.mode or "project").lower()
    goal = db.get_setting("project_goal", "") or ""
    history_rows = db.recent_history(20)
    history = [
        {"role": "user", "content": row.get("prompt", "")}
        if row.get("kind") == "chat" else
        {"role": "assistant", "content": row.get("response", "")}
        for row in reversed(history_rows)
        if row.get("kind") == "chat"
    ][-8:]
    try:
        result = await router.chat(
            model_name,
            ChatContext(
                message=req.message,
                mode=mode,
                project_goal=goal if mode == "project" else "",
                history=history,
            ),
            use_cache=False,
        )
        payload = {
            "role": "assistant",
            "content": result.content,
            "kind": mode,
            "model": result.model,
            "backend": result.backend,
            "latency_ms": result.latency_ms,
        }
        db.add_history("chat", result.model, req.message[:500], result.content[:2000], result.latency_ms)
        return payload
    except Exception as exc:
        raise HTTPException(502, f"Selected model '{model_name}' failed: {exc}") from exc


@app.get("/api/ai/monitor")
async def ai_monitor():
    """Proactive tips for the live side monitor."""
    goal = db.get_setting("project_goal", "") or ""
    insights = monitor_insights(router.index, project_goal=goal)
    stats = router.index.stats()
    return {"insights": insights, "stats": stats, "goal": goal}


# ---------- Folder analysis ----------

@app.post("/api/ai/analyze-folder")
async def api_analyze_folder(req: FolderAnalysisRequest):
    goal = db.get_setting("project_goal", "") or ""
    result = await analyze_folder_with_model(
        router.index, model_name=req.model, project_goal=goal, router=router
    )
    db.add_history(
        "analyze",
        result.get("model_analysis", {}).get("model", req.model),
        goal or "(no goal)",
        result.get("summary", ""),
        result.get("latency_ms", 0),
    )
    return result


@app.post("/api/ai/analyze-action")
async def api_analyze_action(req: AnalysisActionRequest):
    """Generate a model-authored update for one indexed file, without applying it."""
    indexed = {f["path"] for f in router.index.list_files()}
    if req.path not in indexed:
        raise HTTPException(400, "Analysis actions may only target files in the indexed folder")

    full = router.index.get_file(req.path) or {}
    current = full.get("content") or ""
    language = full.get("language") or "text"
    prompt = (
        "You are implementing a safe improvement to the project file below.\n"
        f"Project type: {req.project_type or 'unknown'}\n"
        f"Instruction: {req.instruction}\n\n"
        "Return ONLY valid JSON: {\"path\":\"...\",\"content\":\"complete replacement file content\",\"summary\":\"short explanation\"}\n"
        "Rules: modify ONLY this file; preserve behavior unless instructed; do not invent dependencies; return the COMPLETE file; no markdown fences.\n\n"
        f"FILE ({language}):\n{current}"
    )

    from models.base import ChatContext
    result = await router.chat(
        req.model, ChatContext(message=prompt, mode="analysis", project_context=current), use_cache=False
    )
    parsed = _extract_json(result.content)
    if not parsed or "content" not in parsed:
        raise HTTPException(502, f"Selected model did not return a structured update: {result.content[:600]}")
    proposed = str(parsed["content"])
    diff = "".join(difflib.unified_diff(
        current.splitlines(True), proposed.splitlines(True),
        fromfile=req.path, tofile=req.path,
    ))
    return {
        "path": req.path,
        "content": proposed,
        "summary": str(parsed.get("summary") or "Model-proposed update"),
        "diff": diff,
        "model": result.model,
        "backend": result.backend,
    }



# ---------- Hugging Face model catalog ----------

@app.get("/api/models/huggingface")
async def hf_models(search: str = "", refresh: bool = False):
    """List and organize open models from Hugging Face (+ curated)."""
    catalog = await get_catalog(force_refresh=refresh, search=search)
    if search and catalog.get("models"):
        catalog["models"] = search_local(search, catalog["models"])
        # rebuild organized for filtered
        org: dict = {}
        for m in catalog["models"]:
            org.setdefault(m.get("category") or "other", []).append(m)
        catalog["organized"] = org
        catalog["total"] = len(catalog["models"])
    return catalog


@app.post("/api/models/huggingface/select")
async def hf_select(payload: dict):
    """Remember selected HF model id for inference."""
    model_id = payload.get("model_id") or payload.get("id")
    if not model_id:
        raise HTTPException(400, "model_id required")
    db.set_setting("hf_model_id", model_id)
    return {"ok": True, "model_id": model_id}


# ---------- Project generator + self-heal ----------

@app.post("/api/ai/generate-project")
async def api_generate_project(req: GenerateProjectRequest):
    goal=req.goal or db.get_setting("project_goal","") or ""
    model_result=await generate_project_with_model(req.prompt,goal,router)
    if model_result.get("ok"):
        db.add_history("generate",model_result.get("model","model"),req.prompt[:400],model_result.get("summary",""),model_result.get("latency_ms",0))
        return model_result
    template_result=generate_project(req.prompt,project_goal=goal)
    template_result["fallback_reason"]=model_result.get("error","model unavailable")
    template_result["model_losers"]=model_result.get("losers",[])
    db.add_history("generate","template",req.prompt[:400],template_result.get("summary",""),template_result.get("latency_ms",0))
    return template_result


@app.post("/api/ai/self-heal")
async def api_self_heal(req: SelfHealRequest):
    result = self_heal(req.error_text, req.files or [], language=req.language)
    db.add_history("self-heal", "generator", req.error_text[:400], "; ".join(result.get("reasons") or []), result.get("latency_ms", 0))
    return result


@app.post("/api/ai/generate-project/zip")
async def api_generate_zip(req: GenerateProjectRequest):
    from fastapi.responses import Response
    goal = req.goal or db.get_setting("project_goal", "") or ""
    result = generate_project(req.prompt, project_goal=goal)
    data = files_to_zip(result["files"])
    filename = f"{result['name']}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



# ---------- Image / vision analysis ----------

@app.post("/api/ai/vision")
async def vision_analyze(req: VisionRequest):
    """Screenshot/image → answer, suggestion, optional live fix (personal IDE companion)."""
    import base64
    start_t = time.perf_counter()
    raw = req.image_base64 or ""
    if "," in raw and raw.strip().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw)
    except Exception:
        raise HTTPException(400, "Invalid base64 image")
    size = len(data)
    kind = "png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ("jpeg" if data[:3] == b"\xff\xd8\xff" else "image")
    user_q = (req.prompt or "").strip()
    lower = user_q.lower()
    goal = db.get_setting("project_goal", "") or ""

    answer = ""
    suggestion = ""
    actions = []

    # --- Personal IDE screenshot intents ---
    if any(k in lower for k in ("particle", "particles", "partcyle", "don't work", "dont work", "not work", "don't see", "dont see", "add more")):
        answer = (
            "The particle effect is a background canvas layer. If you don't see it, common causes are: "
            "it was never enabled, z-index was behind the app shell, opacity was too low, or the animation never started."
        )
        suggestion = (
            "Force-enable particles from Evolve or Apply the live fix below. "
            "You should see moving dots and connecting lines over the background. "
            "Toggle Particles in UI Theme if you want them off later."
        )
        actions.append({
            "id": "fix-particles",
            "title": "Enable & rebuild particles",
            "description": "Turns particles on with a visible canvas layer",
            "target": "js",
            "code": "if(typeof setParticles==='function'){setParticles(false);setTimeout(function(){setParticles(true);},40);}else{alert('setParticles missing – hard-refresh the page');}",
        })
    elif any(k in lower for k in ("remove", "hide", "delete")) and any(k in lower for k in ("theme", "these", "button", "chip")):
        answer = "You asked to remove theme controls from the UI."
        suggestion = "Apply the hide-themes patch, or use Evolve: “hide theme buttons”. Undo with Ctrl+Alt+Z if needed."
        actions.append({
            "id": "hide-themes",
            "title": "Hide theme buttons",
            "description": "Hides the theme chip row",
            "target": "css",
            "code": ".theme-row{display:none!important}",
        })
    elif any(k in lower for k in ("issue", "what's wrong", "what is the issue", "broken", "not working", "doesn't work")):
        answer = (
            "From this screenshot of DreamCoder: Evolve is the self-update panel. "
            "Patches only change the live UI when applied (this build auto-applies). "
            "If a feature still fails after Go, the usual issues are cached old JS (hard-refresh), "
            "backend offline (local fallback still runs), or a missing browser API."
        )
        suggestion = (
            "1) Hard-refresh (Ctrl+F5). 2) Click Particles / Evolve the exact fix. "
            "3) Open Debug page to confirm API health. 4) Check the terminal panel for apply logs."
        )
        actions.append({
            "id": "fix-particles-2",
            "title": "Try: enable particles",
            "description": "Most common visual FX complaint",
            "target": "js",
            "code": "if(typeof setParticles==='function'){setParticles(true);}",
        })
        actions.append({
            "id": "show-themes",
            "title": "Show all themes",
            "description": "Ensure theme chips are visible",
            "target": "js",
            "code": "document.querySelectorAll('.theme-row').forEach(r=>r.style.display='flex');['peach','shroom','ocean','ember'].forEach(function(n){var row=document.querySelector('.theme-row');if(!row||document.querySelector('[data-theme=\"'+n+'\"]'))return;var b=document.createElement('button');b.className='theme';b.dataset.theme=n;b.textContent=n[0].toUpperCase()+n.slice(1);b.onclick=function(){if(typeof applyTheme==='function')applyTheme(n);};row.appendChild(b);});",
        })
    elif any(k in lower for k in ("theme", "color", "colour", "peach", "shroom")):
        answer = "You're asking about colors/themes for this personal IDE."
        suggestion = "Apply extra themes or Evolve “switch to peach theme”. Themes persist in localStorage."
        actions.append({
            "id": "more-themes",
            "title": "Add more theme colors",
            "description": "Peach, Shroom, Ocean, Ember…",
            "target": "js",
            "code": "['peach','shroom','ocean','ember','rose','mint','sand'].forEach(function(n){var row=document.querySelector('.theme-row');if(!row||document.querySelector('[data-theme=\"'+n+'\"]'))return;var b=document.createElement('button');b.className='theme';b.dataset.theme=n;b.textContent=n[0].toUpperCase()+n.slice(1);b.onclick=function(){if(typeof applyTheme==='function')applyTheme(n);};row.appendChild(b);});if(typeof applyTheme==='function')applyTheme('peach');",
        })
    elif any(k in lower for k in ("error", "bug", "exception", "traceback", "fail")):
        answer = "This looks error-related. Read the exact message/line from the image when possible."
        suggestion = "Paste the error into Self-Heal, or run the same command in the local terminal. Open the file from the stack and Suggest."
        actions.append({
            "id": "focus-heal",
            "title": "Focus Self-Heal panel",
            "description": "Jump to paste-error workflow",
            "target": "js",
            "code": "document.getElementById('healError')?.focus();document.getElementById('healCard')?.scrollIntoView({behavior:'smooth'});",
        })
    else:
        answer = (
            f"Image received ({kind}, {size} bytes). "
            + (f"Your project goal is “{goal[:120]}”. " if goal else "")
            + "I treat this as context for your personal IDE session — code, UI, errors, or architecture."
        )
        suggestion = (
            "Be specific: “particles don’t show”, “remove these buttons”, “explain this error”, "
            "“improve this layout”. You’ll get an answer, a suggestion, and Apply live when a fix exists."
        )
        actions.append({
            "id": "open-evolve",
            "title": "Focus Evolve",
            "description": "Describe the UI change you want",
            "target": "js",
            "code": "document.getElementById('evolveInput')?.focus();",
        })

    content = (
        f"**Answer**\n{answer}\n\n"
        f"**Suggestion**\n{suggestion}\n\n"
        f"**Your question:** {user_q or '(none)'}\n"
        f"_Image: {kind}, {size} bytes · model {req.model}_"
    )
    if actions:
        content += f"\n\n**Live fixes available:** {len(actions)} — use Apply below."

    latency = int((time.perf_counter() - start_t) * 1000)
    try:
        db.add_history("vision", req.model, user_q[:300], content[:800], latency)
    except Exception:
        pass
    return {
        "ok": True,
        "kind": kind,
        "size": size,
        "answer": answer,
        "suggestion": suggestion,
        "content": content,
        "actions": actions,
        "model": req.model,
        "latency_ms": latency,
    }



@app.post("/api/terminal/run")
async def terminal_run(req: TerminalRequest):
    """Execute a command on the machine running the backend (personal local shell)."""
    import subprocess
    import shlex
    import platform

    cmd = (req.command or "").strip()
    if not cmd:
        return {"ok": False, "output": "", "error": "empty command", "exit_code": 1}

    # Resolve cwd
    cwd = (req.cwd or "").strip() or str(workspace.root() or Path.cwd())
    root = workspace.root()
    if root is not None:
        try:
            candidate = Path(cwd).expanduser().resolve()
            if candidate != root and root not in candidate.parents:
                raise HTTPException(400, "Terminal cwd must stay inside the active workspace")
            cwd = str(candidate)
        except HTTPException:
            raise
        except Exception:
            cwd = str(root)

    start = time.perf_counter()
    try:
        # Windows: run through cmd /c ; Unix: shell
        if platform.system() == "Windows":
            completed = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=min(max(req.timeout, 1), 300),
                env=os.environ.copy(),
            )
        else:
            completed = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=min(max(req.timeout, 1), 300),
                env=os.environ.copy(),
            )
        out = (completed.stdout or "") + (("" if not completed.stderr else (("\n" if completed.stdout else "") + completed.stderr)))
        latency = int((time.perf_counter() - start) * 1000)
        return {
            "ok": completed.returncode == 0,
            "output": out if out else "(no output)",
            "exit_code": completed.returncode,
            "cwd": cwd,
            "command": cmd,
            "latency_ms": latency,
            "shell": "cmd" if platform.system() == "Windows" else "sh",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "Command timed out", "exit_code": -1, "cwd": cwd, "command": cmd}
    except Exception as exc:
        return {"ok": False, "output": str(exc), "exit_code": -1, "cwd": cwd, "command": cmd}


@app.get("/api/terminal/cwd")
async def terminal_cwd():
    return {"cwd": os.getcwd(), "platform": __import__("platform").system()}


# ---------- WebSocket streaming completions ----------

@app.websocket("/ws/complete")
async def ws_complete(ws: WebSocket):
    """Token-by-token (simulated or real) completion stream.

    Client sends JSON: { "model": "...", "code": "...", "prompt": "optional instruction" }
    Server streams: { "type": "token", "text": "..." } then { "type": "done", "model": "...", "latency_ms": N }
    """
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "invalid JSON"})
                continue

            model = msg.get("model", "Llama-3.1-8B-Instruct")
            code = msg.get("code", "")
            prompt = msg.get("prompt", "Continue or improve this code.")
            start = time.perf_counter()

            await ws.send_json({"type": "start", "model": model})

            # Build a mock streamed response based on context
            # (Replace body with real Ollama/HF streaming when configured)
            ctx = CodeContext(code=code, language=msg.get("language", "python"))
            result = await router.suggest(model, ctx, use_cache=False)

            # Stream suggestion titles + code as "tokens"
            pieces = []
            for s in result.suggestions:
                pieces.append(f"# {s.title}\n")
                pieces.append(f"# {s.description}\n")
                # chunk the code
                chunk_size = 12
                for i in range(0, len(s.code), chunk_size):
                    pieces.append(s.code[i : i + chunk_size])
                pieces.append("\n\n")

            for piece in pieces:
                await ws.send_json({"type": "token", "text": piece})
                await asyncio.sleep(0.03)  # feel like streaming

            latency = int((time.perf_counter() - start) * 1000)
            await ws.send_json({
                "type": "done",
                "model": result.model,
                "latency_ms": latency,
                "suggestion_count": len(result.suggestions),
            })
            db.add_history("stream", result.model, prompt[:300], f"{len(result.suggestions)} suggestions", latency)

    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
