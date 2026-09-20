# DreamCoder

DreamCoder is a local AI-native development studio: a FastAPI backend plus a browser/Electron frontend for coding, project indexing, model-driven suggestions, folder analysis, project agents, and live GitHub sync.

This repo is the real application code, not just a static demo shell. The frontend talks to a live backend on port 8000, and the backend can discover real model providers, inspect your workspace, run tooling, and push selected changes to GitHub.

## What this project really is

DreamCoder combines:

- a browser-based IDE shell in [frontend/](frontend/)
- a Python FastAPI service in [backend/](backend/)
- a local project index stored in SQLite
- model routing for Ollama, HuggingFace, OpenAI-compatible APIs, and a mock/offline mode
- project-level chat and folder analysis
- an agent workflow with approval before applying changes
- optional live GitHub autosync for the currently configured repo/branch
- an Electron desktop wrapper in [electron/](electron/)

The app is designed to run locally, with the backend serving the actual API and the frontend acting as the UI layer.

---

## Quick start

### 1. Install dependencies

```bash
cd /path/to/DreamCoder
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start the backend

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

The backend should be reachable at:

- http://127.0.0.1:8000
- docs: http://127.0.0.1:8000/docs

### 3. Start the frontend

There are two practical ways to open the UI:

#### Option A: open the static frontend directly

```bash
cd frontend
python -m http.server 8001
```

Then open:

- http://127.0.0.1:8001/index.html

#### Option B: use the bundled browser route with the backend

The frontend uses `window.DREAMCODER_API` when present. If the page still shows offline or unreachable, open the browser console and run:

```js
window.DREAMCODER_API = "http://127.0.0.1:8000";
location.reload();
```

### Windows launcher

A ready-to-use batch file is included at [start_dreamcoder_windows.bat](start_dreamcoder_windows.bat).

Double-click it from Windows to launch:

- backend on 127.0.0.1:8000
- frontend on 127.0.0.1:8001
- browser open to the app

---

## Core features

### AI-powered coding workflow

- code editor and terminal in the same local workspace
- single-model suggestions and multi-model ask-all flows
- run/test actions inside the IDE
- project-aware chat and folder analysis
- AI-generated patches and local project healing

### Project indexing

The backend maintains a local project index in SQLite, including:

- files discovered in the loaded workspace
- code symbols for navigation and awareness
- saved chat/project context
- project state across app restarts

### Model routing

DreamCoder can route to providers such as:

- Ollama
- Hugging Face
- OpenAI-compatible APIs
- mock/offline mode for local development

The selected provider is surfaced in the UI and can be checked live from the model status indicator.

### GitHub sync

GitHub sync is optional but supported for direct repo mirroring from the running backend.

Typical environment variables:

```bash
export GITHUB_TOKEN="..."
export DREAMCODER_GITHUB_REPO="PcButNoBTC/DreamCoder"
export DREAMCODER_GITHUB_BRANCH="main"
export DREAMCODER_GITHUB_AUTOSYNC="true"
```

For Windows CMD, the equivalent is:

```bat
set GITHUB_TOKEN=...
set DREAMCODER_GITHUB_REPO=PcButNoBTC/DreamCoder
set DREAMCODER_GITHUB_BRANCH=main
set DREAMCODER_GITHUB_AUTOSYNC=true
```

Optional OAuth-related settings may also be used for the GitHub auth flow:

```bash
export DREAMCODER_GITHUB_CLIENT_ID="..."
export DREAMCODER_GITHUB_CLIENT_SECRET="..."
export DREAMCODER_OAUTH_STATE_SECRET="..."
export DREAMCODER_GITHUB_CALLBACK="http://127.0.0.1:8000/api/github/oauth/callback"
```

The backend exposes status at:

- http://127.0.0.1:8000/api/github/status
- http://127.0.0.1:8000/api/github/oauth/config

### Agent workflow

The project agent runs in a workspace-bound loop with explicit tool access, approval steps, and validation. It can:

- read files
- search the repo
- patch files
- run commands in a safe allowlist
- review git status and diffs
- return results for approval before applying changes

---

## Architecture

```text
Browser / Electron UI
       |
       v
FastAPI backend (backend/main.py)
       |
       +--> model router / provider adapters
       +--> SQLite project index and workspace metadata
       +--> agent runtime and approval flow
       +--> folder analysis / chat / AI suggestions
       +--> GitHub sync and OAuth status
       +--> local terminal / file operations
```

---

## Repository layout

```text
DreamCoder/
├── backend/              # FastAPI API and app logic
├── frontend/             # static web UI shell
├── electron/             # desktop app wrapper
├── scripts/              # local helper scripts
├── requirements.txt      # Python dependencies
├── README.md             # project overview
├── start_dreamcoder_windows.bat
├── pytest.ini
├── SETUP.md
├── CHANGES.md
└── PRODUCTION.md
```

---

## Typical local workflow

1. Start the backend.
2. Open the frontend in the browser.
3. Pick a model/provider from the selector.
4. Open or drop a folder.
5. Use chat, suggestions, analysis, or the agent.
6. Optionally enable GitHub sync to push repo updates.

---

## Important note

If the app shows Offline / Unavailable in the UI, that usually means the browser is hitting the wrong host. The full app depends on the live backend, not the GitHub Pages shell alone.

Use the backend URL directly:

```js
window.DREAMCODER_API = "http://127.0.0.1:8000";
location.reload();
```

This repo is intended to be run locally as a functional AI development environment with real backend services behind it.
