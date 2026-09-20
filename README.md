# DreamCoder

DreamCoder is an AI-native creation engine for software projects. It combines a browser-based IDE, a FastAPI backend, project indexing, multi-model reasoning, live suggestions, and safe self-healing workflows so a user can move from idea → project → validation → refinement with less friction.

The app is designed to act like a practical AI software teammate, not just a shell for one prompt. It can reason about a live workspace, evaluate the right model for the task, propose code changes, apply safe insertions, and support a generation/repair loop that keeps the project moving.

## What DreamCoder already does

- browser IDE experience in [frontend/](frontend/)
- Python backend in [backend/](backend/)
- workspace indexing and project context extraction
- multi-provider model routing across Ollama, Hugging Face, and OpenAI-compatible APIs
- live suggestions with apply/preview/ignore interactions
- folder analysis and project-level recommendations
- project generation and build validation workflows
- checkpointing, sync hooks, and safe editor recovery
- optional GitHub integration and agent-style review flows

> The goal is not just “chat with AI” — it is to build a system that helps create, inspect, validate, and improve software while staying grounded in the actual project.

---

## Why this is the right direction

The biggest project-development win with AI is not a large single prompt. It is a loop:

1. understand the project
2. propose a next move
3. inspect the exact file / context
4. apply or preview a change
5. validate it
6. keep a memory of decisions and outcomes

That loop makes AI useful for everything from a tiny utility to a full product. The app is already aligned with this structure.

---

## How to make project development easier with AI

DreamCoder becomes far more useful when it behaves like a system, not a toy assistant.

### 1. Goal-first project creation

Every project should begin with a concrete mission: “build an app”, “refactor this backend”, “make this tool faster”, “generate a dashboard”, “create a CLI for X”. The AI should turn that goal into:

- a project structure
- a tech stack recommendation
- a likely file layout
- a task plan
- validation steps
- rollback checkpoints

### 2. Whole-project understanding

The app should analyze the whole folder, not just the current file. That means:

- file graph and dependency awareness
- symbol / module / API recognition
- repeated patterns across the codebase
- architecture suggestions based on actual project shape
- high-value recommendations before edits are made

### 3. Multi-model reasoning

Different tasks need different models:

- code generation for a specific feature
- reasoning about architecture or refactors
- summarization and project explanation
- validation and test generation
- bug repair loops

The project should rank or route models by task, not always default to one model for everything.

### 4. Human review loops

AI should propose, not silently impose. A strong creation system has:

- Apply / Preview / Ignore actions
- approval gates for larger changes
- diff previews before mutation
- automatic rollback when the result fails
- human confirmation for risky edits

### 5. Safe execution and validation

A creation system must validate each result in a running context:

- compile or run generated code
- run tests when possible
- catch failure signals early
- repair broken outputs using the actual error trace
- preserve a rollback point before applying big changes

### 6. Persistent project memory

The system becomes far more useful if it remembers:

- project goals
- architecture decisions
- recurring patterns
- prior fixes and failed approaches
- which models worked best for which kind of task

This turns the assistant from a one-off prompt engine into a project collaborator.

---

## What would make DreamCoder truly great for creating anything

If the project is meant to be a general creation engine, it should support more than just coding tasks. It should become a workflow for turning intention into working artifacts.

### Ideal creation loop

1. prompt or goal
2. project / folder context
3. architecture selection
4. generation or scaffolding
5. validation and failure repair
6. iteration with feedback
7. save / sync / checkpoint / share

### Potential product scope

DreamCoder can support:

- web apps and landing pages
- CLI tools and scripts
- APIs and backend services
- data dashboards and analytics tools
- internal enterprise tooling
- automation workflows
- prototypes and experiments
- learning tools and educational projects
- small game loops, simulations, and utilities

The central principle is simple: if a user can describe a desired outcome, the system should help convert that outcome into working project structure, code, tests, and refinements.

---

## Current status

The project already behaves like a local AI coding workspace with:

- backend startup on port 8000
- frontend served locally
- model selection and live provider fallback
- Ollama awareness and fallback behavior
- Hugging Face token and catalog support
- build generation with validation and safe fallback when sandbox runtime is unavailable
- suggestion previews and review actions
- agent-style project workflows and project indexing

This is no longer only a prototype. It is an active foundation for a much broader AI creation environment.

---

## Quick start

### Windows

```bat
start_dreamcoder_windows.bat
```

### Manual setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start backend:

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Start frontend:

```bash
cd frontend
python -m http.server 8001
```

Open:

```text
http://127.0.0.1:8001/index.html
```

API docs:

```text
http://127.0.0.1:8000/docs
```

---

## Provider notes

### Ollama

Local models can be used through Ollama when the server is reachable.

### Hugging Face

HF model IDs are supported for real provider-backed behavior and can be selected from the app when available.

### OpenAI-compatible

OpenAI-compatible model endpoints can be used when configured through environment settings.

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
│   ├── generator.py
│   ├── workspace.py
│   └── ...
├── frontend/
├── electron/
├── scripts/
├── README.md
├── CHANGES.md
├── PRODUCTION.md
├── SETUP.md
├── requirements.txt
├── pytest.ini
├── start_dreamcoder_windows.bat
├── start_dreamcoder_no_credit.bat
└── .gitignore
```

---

## The path to an ideal AI creation platform

The best version of DreamCoder is not just an editor with a chatbot bolted on. It is a creation loop that can:

- understand an entire codebase
- choose the right model for each task
- make safe project changes
- validate the result
- explain what was done and why
- learn from previous decisions
- operate with checkpoints and approvals

That is the difference between a useful assistant and a real creation system.

## Unified change engine


DreamCoder now has the foundations of a durable change lifecycle:

**Inspect → Plan → Contract → Patch → Review → Validate → Repair → Approve → Git**


- ChangePlan provides a canonical, serializable change contract.
- Existing-project agent writes use patch preconditions so stale files are rejected instead of silently overwritten.
- Generation task dependencies now pass upstream artifact summaries to downstream specialists.
- Generation results expose patch metadata and a ChangePlan record.
- Persistent generation jobs provide job IDs, durable status, event history and cancellation.
- Model/provider telemetry records latency and success/failure for explainable routing.
- Project health exposes evidence-based workspace, Git, test-discovery and project signals.
- Production CORS defaults to local DreamCoder origins and can be configured with DREAMCODER_CORS_ORIGINS.

See docs/ARCHITECTURE_NEXT.md and docs/ROADMAP_EXPANDED.md.
