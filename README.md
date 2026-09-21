# DreamCoder

**DreamCoder is an AI-native development studio for turning an idea into a real, validated software project.**

Instead of treating AI as a single chat box that writes one file at a time, DreamCoder is built around a durable development workflow: understand the goal, create a project, plan the work, route each task to the right model, generate changes, validate them, repair failures, preserve decisions and checkpoints, and keep the project documented.

## What DreamCoder is

DreamCoder combines a browser-based development environment, a FastAPI backend, project intelligence, multi-model orchestration, Model Lab benchmarking, Project Hub memory, task-graph execution, validation, Git workflows, and durable execution infrastructure.

The core idea is simple:

> **Describe what you want to build. DreamCoder turns that intent into an organized software-development process.**

It is designed for everything from small utilities and prototypes to larger multi-file applications and ongoing repositories.

---

## The development loop

DreamCoder is organized around a visible lifecycle:

**Goal → Plan → Generate → Validate → Review → Apply → Checkpoint → Git**

Under the hood, the change lifecycle is even more explicit:

**Inspect → Plan → Contract → Patch → Review → Validate → Repair → Approve → Git**

This makes AI development a process rather than a one-shot generation request.

### 1. Start with a goal

A user can describe an outcome in natural language: build an application, add a feature, refactor a subsystem, create an API, investigate a bug, or improve an existing repository.

DreamCoder can turn that intent into project requirements, tasks, architecture context, and validation work.

### 2. Understand the project

DreamCoder works with actual workspace and repository context instead of relying only on a prompt.

Project intelligence can include:

- files and folders
- project structure
- dependencies and relationships
- repository state
- requirements
- decisions
- generated artifacts
- task history
- validation evidence
- checkpoints and releases

### 3. Plan the work

The project can be decomposed into tasks with roles, dependencies, inputs, outputs, and model assignments.

This provides a foundation for multi-step development instead of forcing every task through one giant prompt.

### 4. Use different models for different jobs

DreamCoder includes a **Model Registry** and **Model Lab**.

Models can be evaluated for roles such as:

- planning
- generation
- debugging
- testing
- documentation
- repository reasoning
- tool-use planning
- review

The router uses measured benchmark evidence and model lifecycle information to select eligible models. Projects can also explicitly pin a model for a role when desired.

Supported provider paths include local/Ollama, Hugging Face, and OpenAI-compatible endpoints, with the architecture designed for additional providers.

### 5. Generate changes

Generation is treated as a project operation rather than isolated text output.

DreamCoder can preserve:

- task context
- upstream artifact summaries
- requested and selected models
- change-plan metadata
- project provenance
- generation events

Patch preconditions and reviewable change flows help prevent stale project state from being silently overwritten.

### 6. Validate with evidence

DreamCoder is designed to check generated work against the real project.

Validation can include:

- executable benchmark evidence
- compilation/build checks
- tests and test discovery
- repository/project health signals
- sandbox-backed execution
- model telemetry
- failure information for repair workflows

The objective is to distinguish **“the model said it works”** from **“the project produced evidence that it works.”**

### 7. Repair failures

Failures can become inputs to later debugging or repair tasks.

The longer-term architecture is a feedback loop:

**Generate → Run → Observe failure → Diagnose → Repair → Validate again**

This is one of the key differences between an AI coding assistant and an AI development system.

### 8. Review and approve

DreamCoder keeps humans in the loop for important project changes.

The UI and change system support reviewable actions such as:

- Apply
- Preview
- Ignore
- diff/change inspection
- approval gates
- checkpoints
- rollback-oriented workflows

### 9. Preserve project memory

The **Project Hub** gives each project a durable record.

It can track:

- project goal and original prompt
- requirements
- sessions
- events/timeline
- living documents
- decisions and rationales
- artifacts
- task graph
- model assignments
- checkpoints
- releases
- provenance

This means a project does not have to be reconstructed from scratch every time the user returns.

### 10. Execute work durably

DreamCoder now has a persistent execution queue.

Jobs can be:

- queued
- prioritized
- claimed by workers
- retried
- cancelled
- completed
- failed with stored error information

Project tasks can execute through the queue using their assigned models, with durable task status and output.

The goal is for long-running AI development work to survive process restarts instead of disappearing with an in-memory request.

---

## Model Lab: evidence-driven model orchestration

Model choice is a first-class part of DreamCoder.

Model Lab provides:

- model registration
- provider and revision metadata
- benchmark cases
- role-specific scores
- executable evidence
- repeatable benchmark runs
- revision regression tracking
- stale-evidence detection
- routing profiles
- model health
- runtime/resource observability
- advisory evaluator summaries

### Important routing principle

The router is **evidence-driven**.

Measured benchmark results determine eligibility. Local evaluator summaries can explain structured benchmark evidence, but evaluator prose does not override measured eligibility.

This makes model routing more inspectable and reproducible.

---

## Project Hub: the living project record

Project Hub is the persistent center of a DreamCoder project.

Instead of keeping the project state scattered across chat history, editor state, and temporary files, DreamCoder can preserve the important development record in structured form.

A project can accumulate a living history of:

**Goal → Requirements → Decisions → Tasks → Model assignments → Artifacts → Validation → Checkpoints → Releases**

That foundation enables future features such as richer project resumes, dependency-aware planning, release automation, and deeper project analytics.

---

## Task Graph and multi-agent foundations

DreamCoder's task graph represents development as connected work rather than a flat list of prompts.

Tasks can carry:

- role
- title
- description
- status
- dependencies
- inputs
- outputs
- assigned model
- attempt information
- provenance

This allows different specialists to work on different parts of a project while preserving the relationships between their outputs.

The intended architecture supports workflows such as:

**Planner → Architect → Generator → Tester → Debugger → Reviewer → Release**

The model used for each role can be selected independently according to project preferences and measured evidence.

---

## Safety, sandboxing, and controlled execution

DreamCoder includes infrastructure for controlled execution and review.

The sandbox is hardened with controls such as:

- read-only container operation
- dropped Linux capabilities
- no-new-privileges
- process limits
- memory/CPU limits
- non-root execution
- temporary filesystem isolation
- workspace-scoped writable access
- network disabled by default

Safety assessment and independent review can also be used in generation workflows.

The intent is to make AI-powered development more observable and controllable, especially when generated work needs to be executed.

---

## Git and repository workflows

DreamCoder is designed to work with real repositories rather than isolated generated snippets.

The broader workflow includes:

- project/repository context
- Git state awareness
- checkpoints
- change review
- synchronization hooks
- Git-oriented task roles
- provenance
- release-oriented workflows
- optional GitHub integration

The long-term target is a complete path from:

**Idea → Project → Changes → Validation → Checkpoint → Commit → Pull Request → Release**

---

## Provider and runtime architecture

DreamCoder is built to support multiple model backends rather than locking the application to one provider.

Current provider-oriented capabilities include:

- Ollama/local models
- Hugging Face model IDs
- OpenAI-compatible endpoints
- provider runtime retries
- request timeouts
- concurrency controls
- model telemetry
- runtime health information
- model discovery

This enables the system to combine local and remote models according to project requirements and available infrastructure.

---

## Observability

DreamCoder records structured evidence about important operations.

Examples include:

- model latency
- success/failure
- benchmark results
- model revisions
- routing decisions
- task status
- queue state
- project events
- generation lifecycle
- validation evidence
- checkpoints and provenance

The purpose is explainability: when DreamCoder makes an orchestration decision, the system should be able to show the project context and evidence behind it.

---

## What you can build with DreamCoder

DreamCoder is intended as a general software-development environment, not a single-purpose code generator.

Examples include:

- web applications
- APIs and backend services
- dashboards
- CLI tools
- automation utilities
- internal business tools
- data-processing applications
- developer tooling
- prototypes
- educational software
- simulations
- games and interactive applications
- existing-repository refactors and feature work

The exact result depends on the project requirements, available models, runtime environment, validation coverage, and human review.

---

## Architecture at a glance

```text
                         ┌──────────────────────┐
                         │       User Goal      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     Project Hub      │
                         │ goals / docs / state │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      Task Graph      │
                         │ roles / dependencies │
                         └──────────┬───────────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                ┌─────────────────┐   ┌─────────────────┐
                │    Model Lab    │   │ Project Model   │
                │ benchmarks      │   │ preferences     │
                │ evidence        │   │ pinned / auto   │
                └────────┬────────┘   └────────┬────────┘
                         └──────────┬──────────┘
                                    ▼
                         ┌──────────────────────┐
                         │   Evidence Router    │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Durable Execution    │
                         │ queue / retry / job  │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Provider Runtime     │
                         │ local / HF / compat  │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Generate / Execute   │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Validate / Test      │
                         └──────────┬───────────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                  ┌─────────────┐       ┌─────────────┐
                  │ Repair Loop │       │   Review    │
                  └──────┬──────┘       └──────┬──────┘
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Checkpoint / Git     │
                         │ / Release            │
                         └──────────────────────┘
```

---

## Repository structure

```text
DreamCoder/
├── backend/
│   ├── agent/
│   ├── generation/
│   ├── models/
│   ├── tests/
│   ├── ai_router.py
│   ├── execution_queue.py
│   ├── execution_api.py
│   ├── model_lab.py
│   ├── project_hub.py
│   ├── task_graph.py
│   ├── sandbox.py
│   ├── provider_runtime.py
│   └── main.py
├── frontend/
├── electron/
├── scripts/
├── docs/
├── README.md
├── CHANGES.md
├── MODEL_LAB.md
├── PRODUCTION.md
├── SETUP.md
├── requirements.txt
└── pytest.ini
```

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

Start the backend:

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Start the frontend:

```bash
cd frontend
python -m http.server 8001
```

Open:

```text
http://127.0.0.1:8001/index.html
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Configuration and deployment

DreamCoder supports configurable provider, runtime, CORS, model-lab, sandbox, and execution controls.

Important operational settings include:

- model/provider credentials
- AI request timeout
- Model Lab benchmark concurrency
- Model Lab benchmark timeout
- execution queue polling
- CORS origins
- optional Model Lab administration token
- sandbox/runtime configuration

See [SETUP.md](SETUP.md), [PRODUCTION.md](PRODUCTION.md), and [MODEL_LAB.md](MODEL_LAB.md) for environment-specific configuration.

---

## Project direction

DreamCoder is being developed toward a complete AI development studio where software creation is represented as a durable, observable workflow.

The long-term system should be able to:

1. understand a user's intent
2. create or inspect a project
3. build a structured plan
4. select models based on evidence
5. execute independent tasks
6. pass artifacts between tasks
7. run real validation
8. diagnose failures
9. repair the project
10. checkpoint progress
11. preserve decisions and provenance
12. prepare Git changes and releases

The objective is not simply to generate more code.

**The objective is to make the entire software-development process more capable, inspectable, repeatable, and useful.**

---

## Status

DreamCoder already contains substantial foundations for this architecture, including Project Hub, Model Lab, evidence-backed routing, task graphs, provider runtime controls, sandboxing, validation infrastructure, and a durable execution queue.

Some capabilities are production-oriented today; others are active foundations for the next layers of the development studio.

For the current implementation history, see [CHANGES.md](CHANGES.md).
