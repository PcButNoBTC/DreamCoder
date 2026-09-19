# DreamCoder

**Your personal AI-native IDE** — code, prompt, stream, evolve, and query every model from one place.

---

## Quick start (browser)

### 1. Backend
```bash
cd DreamCoder
pip install -r requirements.txt
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend
Open `frontend/index.html` in a browser  
(or `cd frontend && python -m http.server 3000` → http://localhost:3000)

---

## Desktop app (Electron)

```bash
cd DreamCoder/electron
npm install
npm start
```

This launches the UI in a native window and starts the Python backend automatically.

Build installers:
```bash
npm run dist
```

---

## What you can do

| Action | How |
|--------|-----|
| **Run code** | ▶ Run or `Ctrl+Enter` — Python syntax check |
| **Get suggestions** | ✦ Suggest or `Ctrl+Shift+S` |
| **Ask all models** | ◈ Ask All or `Ctrl+Shift+A` — parallel suggestions from Llama, Qwen, DeepSeek, Mistral, Dolphin… |
| **Stream completion** | ≋ Stream or `Ctrl+Shift+T` — token-by-token via WebSocket |
| **Evolve the UI** | ✧ Evolve — describe a change, apply live patches without reload |
| **Switch files** | Click files in the explorer (buffers stay in memory + SQLite index) |
| **Themes** | Midnight / Graphite / Violet |

---

## Architecture

```
UI (browser / Electron)
    │  HTTP + WebSocket
    ▼
FastAPI backend
    ├── AIRouter → Mock / Ollama / HuggingFace adapters
    ├── SuggestionCache (LRU)
    ├── ProjectIndex → SQLite (files + symbols)
    ├── File watcher (watchdog or polling)
    ├── /api/ai/suggest
    ├── /api/ai/suggest-all   ← multi-model parallel
    ├── /ws/complete         ← streaming tokens
    ├── /api/ai/evolve
    └── /api/history
```

---

## Persistent project index (SQLite)

- Location: `backend/data/dreamcoder.db`
- Stores file contents, symbols (classes/functions/vars), and prompt history
- Survives restarts

### Watch a real folder
```bash
curl -X POST http://localhost:8000/api/watch \
  -H "Content-Type: application/json" \
  -d "{\"root\": \"C:/path/to/your/project\"}"
```
Index updates as you save files (watchdog if installed, else polling).

---

## Real models (optional)

### Ollama
```bash
ollama pull llama3.1:8b
set DREAMCODER_LOCAL_BACKEND=ollama
set OLLAMA_MODEL=llama3.1:8b
```

### Hugging Face API
```bash
set HF_TOKEN=hf_xxx
set HF_MODEL=meta-llama/Llama-3.1-8B-Instruct
```

---

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/ai/suggest` | Single-model suggestions |
| POST | `/api/ai/suggest-all` | Parallel multi-model |
| WS | `/ws/complete` | Token streaming |
| POST | `/api/ai/evolve` | Live UI patches |
| POST | `/api/run` | Syntax check |
| GET/POST | `/api/files…` | Indexed files |
| POST | `/api/watch` | Start folder watcher |
| GET | `/api/history` | Past prompts |
| GET | `/api/health` | Status + DB stats |

---

## Project layout

```
DreamCoder/
├── frontend/          # IDE UI
├── backend/
│   ├── main.py        # FastAPI + WebSocket
│   ├── ai_router.py
│   ├── db.py          # SQLite
│   ├── project_index.py
│   ├── watcher.py
│   ├── cache.py
│   ├── data/          # dreamcoder.db (created at runtime)
│   └── models/        # Mock, Ollama, HuggingFace
├── electron/          # Desktop shell
├── scripts/
└── requirements.txt
```

---

## Keyboard shortcuts

| Keys | Action |
|------|--------|
| `Ctrl+Enter` | Run |
| `Ctrl+Shift+S` | Suggest |
| `Ctrl+Shift+A` | Ask all models |
| `Ctrl+Shift+T` | Stream |
| `Ctrl+E` | Focus Evolve |

---

Built to be the IDE you live in: prompt any model, stream completions, keep your index on disk, and evolve the UI from inside the app.

---

## Project context, Live Monitor & Folder Analysis

### Project context
In the AI panel, set:
- **Goal** – what this repo is for (guides every AI reply)
- **Default command** – optional run command for the project

Click **Save context**.

### Live Monitor (side chat)
Always-on panel that:
- Shows project pulse (files, symbols, goal)
- Answers questions about the project or coding in general
- Offers next-step ideas
- Can trigger analysis from chat (“Analyze the folder…”)

Chips: About project · Ideas · Analyze · Next steps

### Folder Analysis
Click **◎ Analyze** (toolbar) or ask the monitor to analyze.
Returns:
- Project-level recommendations aligned to your goal
- Per-file scores, issues, and improvement ideas
- Overall health %

API:
- `GET/POST /api/project/context`
- `POST /api/ai/chat`
- `GET /api/ai/monitor`
- `POST /api/ai/analyze-folder`

## Project-level agent runtime

DreamCoder now exposes a project-scoped agent loop at `/api/agent`.

The runtime separates **planning → approval → tool execution → validation → repair state → diff review** and persists runs, events, and tool calls in SQLite. The agent works inside an explicit workspace boundary and does not receive an unrestricted shell primitive.

### Run an agent task

```bash
curl -X POST http://localhost:8000/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{"goal":"Fix the failing tests and explain the change","cwd":"/path/to/project","auto_apply":false}'
```

Write/patch operations stop at an approval boundary by default. After reviewing the plan, approve the run with `POST /api/agent/runs/{run_id}/approve`.

Agent tools are explicit: `read_file`, `search`, `write_file`, `apply_patch`, `run`, `test`, `git_status`, and `git_diff`. Command execution is restricted to a small development-tool allowlist and paths cannot escape the workspace.

### Model-selected chat

Chat is no longer handled by a hard-coded heuristic responder. Every chat request carries the UI's selected model into the central model router, and the router invokes that model adapter's native conversational interface. Project mode additionally supplies indexed project context and the saved project goal; General mode omits project context.

The chat response reports both the selected model and the backend in the UI. If a model is configured as a mock/offline adapter, DreamCoder labels that explicitly rather than presenting a heuristic answer as real model inference.
