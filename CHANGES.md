# DreamCoder — Change Log

## Product direction

DreamCoder is evolving from an AI coding workspace into an **AI-native development studio**: a system for turning natural-language goals into structured, validated, documented software projects.

The product is organized around:

**Goal → Plan → Generate → Validate → Review → Apply → Checkpoint → Git**

and the underlying change lifecycle:

**Inspect → Plan → Contract → Patch → Review → Validate → Repair → Approve → Git**

## Current capabilities

### Project Hub
- Persistent project registry and project overview.
- Goals, original prompts, requirements, decisions, documents, artifacts, events, checkpoints, and release-oriented provenance.
- Searchable project history and living documentation.

### Multi-model orchestration
- Model Registry with provider, revision, metadata, and lifecycle information.
- Model Lab benchmark suite covering planning, coding, debugging, testing, documentation, repository reasoning, tool-use planning, frontend/API/SQL/container/Git tasks, and boundary consistency.
- Evidence-backed role routing.
- Repeatable benchmark runs and revision regression tracking.
- Project-level automatic or pinned model preferences.
- Advisory evaluator summaries that do not override measured eligibility.

### Task Graph
- Persistent tasks with roles, dependencies, inputs, outputs, status, and model assignments.
- Task-level provenance.
- Foundation for multi-specialist project execution.

### Durable execution
- Persistent execution jobs with priority, retry, cancellation, result, and error state.
- Worker lifecycle integrated with the backend.
- Project task execution through the durable queue.
- Assigned-model execution and durable task output.

### Runtime and observability
- Provider runtime retries, timeouts, concurrency controls, and telemetry.
- Model runtime and health APIs.
- Model discovery.
- Model Lab resource controls.
- Evidence and provenance intended to make orchestration decisions inspectable.

### Generation and change management
- Structured generation lifecycle.
- Change-plan metadata.
- Patch preconditions for existing-project edits.
- Reviewable Apply / Preview / Ignore interactions.
- Validation and repair-oriented workflow foundations.

### Safety and execution controls
- Safety assessment and independent review paths.
- Hardened sandbox configuration.
- Resource/process limits.
- Non-root execution.
- Network disabled by default for sandboxed execution.
- Secure credential and audit-store handling.
- Production readiness checks.

### Git and repository workflows
- Git-aware project context and workflow state.
- Checkpoint and synchronization foundations.
- Optional GitHub integration.
- Release-oriented architecture.

## Product architecture

DreamCoder is intentionally built as several cooperating layers:

1. **Project Hub** — durable project knowledge and provenance.
2. **Task Graph** — structured development work and dependencies.
3. **Model Lab** — measurable model capability evidence.
4. **Evidence Router** — role-aware model selection.
5. **Execution Queue** — durable work execution and retry.
6. **Provider Runtime** — model-provider execution controls.
7. **Generation / Validation** — project changes and objective evidence.
8. **Review / Checkpoint / Git** — human approval and durable project progress.

## Direction of travel

The next layers are centered on:
- real repository build/test/evaluation loops
- richer DAG execution and resume behavior
- continuous model benchmarking and freshness
- model lifecycle and resource accounting
- project-wide validation and repair
- release automation
- richer frontend control-plane visibility
- production authentication and execution limits
- comprehensive CI and end-to-end regression coverage

