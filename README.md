# DreamCoder

DreamCoder is a local-first AI development studio that combines a browser-based IDE, project indexing, multi-provider model routing, workspace automation, and GitHub-aware project workflows in one environment.

It is designed to behave like a practical AI-native coding workspace rather than a single prompt shell. The backend exposes a real FastAPI API, the frontend serves a working browser UI, and the app can use Ollama, Hugging Face, OpenAI-compatible providers, or offline mock mode.

## What DreamCoder is

- a browser UI in [frontend/](frontend/)
- a Python FastAPI backend in [backend/](backend/)
- local project indexing and symbol awareness
- model selection and routing across Ollama, Hugging Face, and OpenAI-compatible APIs
- AI-powered suggestions, chat, folder analysis, and code-generation flows
- project agent workflows with validation and checkpointing
- GitHub sync and workspace-aware project automation
- a desktop wrapper in [electron/](electron/)

> DreamCoder turns natural-language intent into a planned, reviewed, validated, and repairable software workflow.

---

## Current status

The project is already functional as a local AI coding workspace with:

- backend startup on port 8000
- frontend serving on port 8001
- model routing with real provider detection
- dynamic local fallback logic without forcing dead Ollama instances
- Hugging Face token discovery and catalog-based model selection
- launcher scripts that detect and start Ollama automatically
- GitHub sync, workspace checkpointing, and local recovery tools
- agent/project workflows and approval-based execution

This is no longer only a concept demo; it is a working local app scaffold with real backend and model integration paths.

---

## Core capabilities

### Multi-model routing

DreamCoder can route tasks through the correct model provider instead of hard-coding one model for everything.

Supported model sources:

- Ollama
- Hugging Face
- OpenAI-compatible APIs
- offline/mock mode

### Project-aware analysis

The app indexes files, extracts symbols, and keeps project context available for:

- code suggestions
- folder analysis
- fix recommendations
- generation planning
- project understanding across files

### Build → test → repair loop

The generation engine is designed to:

1. generate specialist output
2. integrate it into the project
3. review the result
4. validate or build it
5. capture failures
6. repair using diagnostics
7. re-validate before presenting the result

### Workspace and GitHub automation

DreamCoder includes support for:

- file indexing and save flows
- workspace root configuration
- Git status / diff / branch support
- GitHub OAuth and sync hooks
- local checkpoint and recovery workflows

---

## Quick start

### Windows

From the repository root:

```bat
start_dreamcoder_windows.bat
```

The launcher is designed to:

- detect whether Ollama is installed
- install Ollama if it is missing
- start the local Ollama server
- pull the default model
- fall back to Hugging Face when configured
- launch the backend and frontend automatically

### Manual setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the backend:

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Start the frontend in another terminal:

```bash
cd frontend
python -m http.server 8001
```

Then open:

```text
http://127.0.0.1:8001/index.html
```

API docs are available at:

```text
http://127.0.0.1:8000/docs
```

If the app looks offline, open the browser console and set the API base if needed:

```js
window.DREAMCODER_API = "http://127.0.0.1:8000";
location.reload();
```

---

## Provider details

### Ollama

Use Ollama for local coding models, such as:

```text
ollama:qwen2.5-coder:7b
ollama:tinyllama
```

The local launcher and runtime logic now attempt to ensure the Ollama server is running before the app treats the local backend as ready.

### Hugging Face

Hugging Face model IDs can be used directly in the provider pipeline, for example:

```text
hf:meta-llama/Llama-3.1-8B-Instruct
meta-llama/Llama-3.1-8B-Instruct
```

### OpenAI-compatible endpoints

OpenAI-compatible providers can be configured via environment variables and runtime settings when available.

---

## Project vision and future potential

This project has the potential to become more than a local assistant. Once finished, it could evolve into a full AI-native software studio that behaves more like a team of specialized coding agents than a single chatbot.

### What it could become

A completed DreamCoder could:

- understand an entire repository rather than a single file
- plan multi-step changes across a codebase
- propose architectural refactors with context awareness
- validate changes automatically and summarize results
- keep persistent project memory and design decisions
- work safely inside a local workspace with checkpoints and rollback
- collaborate with GitHub workflows and issue-driven tasks
- support agent-led project generation, test creation, and maintenance

### Real-world impact

The most ambitious version of this project could act as a local software engineer for individuals and small teams:

- build features from a brief
- refactor legacy code while preserving behavior
- explain unfamiliar codebases quickly
- generate tests, docs, and release notes
- maintain a project without constant manual prompting

That is the core promise of DreamCoder: a coding companion grounded in your project, safe in execution, and capable of evolving from helper to collaborator.

---

## Repository layout

```text
DreamCoder/
├── backend/
│   ├── agent/
│   ├── models/
│   ├── main.py
│   ├── ai_router.py
│   ├── analyzer.py
│   ├── workspace.py
│   └── ...
├── frontend/
├── electron/
├── scripts/
├── README.md
├── CHANGES.md
├── requirements.txt
├── start_dreamcoder_windows.bat
├── start_dreamcoder_no_credit.bat
└── .gitignore
```

---

## Validation

The project includes backend tests for provider routing, local model fallbacks, and model-registration logic. A verified local run should keep the app working without silently forcing a dead Ollama instance.

The current state is intended for local development and rapid iteration, not as a guarantee of production-ready deployment without additional validation in the target environment.
│   ├── ai_router.py      # model/provider routing
│   ├── generator.py      # project generation integration
│   ├── project_index.py  # project indexing/context
│   └── ...
├── frontend/             # browser IDE
├── electron/             # desktop wrapper
├── assets/               # DreamCoder branding
├── scripts/              # helper scripts
├── tests/                # automated tests
├── requirements.txt
├── pytest.ini
├── SETUP.md
├── CHANGES.md
├── PRODUCTION.md
└── README.md
=======
## Repository structure

```text
DreamCoder/
├── backend/              # FastAPI API and app logic
├── frontend/             # UI shell served locally
├── electron/             # desktop wrapper
├── scripts/              # helper tooling
├── requirements.txt      # Python dependencies
├── README.md             # project overview and roadmap
├── CHANGES.md            # recent project changes
├── PRODUCTION.md         # production-focused guidance
├── SETUP.md              # setup notes
├── pytest.ini            # test config
├── start_dreamcoder_windows.bat
├── start_dreamcoder_no_credit.bat
└── ...
>>>>>>> 0f01169 (Refresh README and project vision)
```

---

<<<<<<< HEAD
## 🎨 Branding

The project logo is available at:

**`assets/dreamcoder-logo.svg`**

The GitHub/README banner is:

**`assets/dreamcoder-banner.svg`**

The logo is designed to work as the project's primary visual identity, while the banner is intended for GitHub, documentation, and project presentations.
=======
## Typical workflow

1. Start the backend.
2. Start the frontend.
3. Pick a provider from the selector.
4. Open a workspace or project folder.
5. Use suggestions, chat, analysis, or the agent.
6. Review and approve changes when needed.
7. Sync or manage project files via GitHub if configured.
>>>>>>> 0f01169 (Refresh README and project vision)

---

## 🧭 Current development direction

<<<<<<< HEAD
DreamCoder has moved beyond the initial orchestration foundation. The next phase is focused on making the system reliable under real project workloads.

### Immediate priorities
=======
This project is designed to run locally. The backend is the source of truth, and the frontend is only the interface. If the browser shows offline or unreachable, make sure the backend is up on port 8000 and the frontend is served from the correct static directory.

Use:
>>>>>>> 0f01169 (Refresh README and project vision)

1. Run the complete repository test suite in a properly provisioned environment.
2. Exercise real multi-model generation flows.
3. Verify Ollama/Hugging Face/provider routing.
4. Inject build/test failures and verify concrete repair behavior.
5. Verify workspace checkpoints and rollback.
6. Inspect generated diffs for preservation of existing project code.
7. Add/strengthen CI coverage.
8. Improve patch-based incremental generation.
9. Add generation job status and streaming progress.
10. Improve provider reliability, cancellation, retries, and observability.

### Longer-term direction

The larger goal is an AI-native development environment where DreamCoder can:

```text
Understand project
      ↓
Plan change
      ↓
Select specialists
      ↓
Generate targeted changes
      ↓
Integrate
      ↓
Review
      ↓
Build / test
      ↓
Repair
      ↓
Show diff
      ↓
Apply / rollback
```

<<<<<<< HEAD
That means DreamCoder becomes more than a code generator: it becomes a **development loop around the entire project**.

---

## 🛡️ Development philosophy

DreamCoder is designed around a few principles:

- **Model-agnostic** — use the models available to you.
- **Capability-driven** — match work to model strengths.
- **Project-aware** — understand the codebase before changing it.
- **Validation-first** — generated code must face real checks.
- **Repairable** — failures become inputs to the next attempt.
- **Recoverable** — checkpoints provide a safety boundary.
- **Incremental** — prefer targeted changes over unnecessary regeneration.
- **Human-controlled** — the developer remains in charge of applying and shipping changes.

---

## 📌 Project status

DreamCoder is an **active development project**.

The multi-model generation foundation, task graph, capability routing, integration/review stages, validation/repair loop, incremental context, checkpointing, and generation UI are implemented on `main`.

The next milestone is to validate those systems against real projects and harden the implementation based on observed failures.

---

## 📄 License

See the repository's license file for the current licensing terms.

---

<p align="center">
  <img src="assets/dreamcoder-logo.svg" alt="DreamCoder logo" width="96">
</p>

<p align="center">
  <strong>DreamCoder</strong><br>
  <em>Build bigger. Together.</em>
</p>
=======
This repo is intended to be a real local AI development environment rather than a static mock-up.


This repo is intended to be run locally as a functional AI development environment with real backend services behind it.
>>>>>>> 0f01169 (Refresh README and project vision)
