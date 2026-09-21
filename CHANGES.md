# DreamCoder — change log

## Latest updates
- Hardened terminal WebSocket routing so desktop/browser sessions derive the `ws`/`wss` endpoint from the configured DreamCoder API base instead of assuming `hostname:8000`.
- Fixed the generation build path so missing Docker/Podman sandbox runtime no longer turns a valid generated project into a hard failure.
- Added the suggestion review flow with Apply / Preview / Ignore actions to make AI recommendations feel like reviewable project decisions rather than opaque output.
- Refreshed the product positioning so DreamCoder is framed as an AI creation engine for building software from goals, not just as a prompt shell.
- Updated the repo docs to describe the full project-creation loop: understand → plan → generate → validate → refine.
- Kept the local fallback logic resilient when Ollama is missing or unreachable while still supporting real local provider paths.

## Added
- generation validation fallback that still reports success when sandbox runtime is unavailable
- regression tests covering generator builds with no sandbox installed
- project-level guidance in documentation for goal-first AI development
- clearer product framing for multi-model project creation and model-choice improvements

## Changed
- README now focuses on AI-native creation workflows instead of only local IDE status
- project docs now emphasize whole-project analysis, validation loops, and approval-driven edits
- suggestion actions are more reviewable and less ambiguous for users
- the vision now extends beyond “one file at a time” toward “build anything from intent” workflows

## Future roadmap
- multi-model project ranking by task type and project context
- persistent project memory across sessions and revisions
- stronger validation and repair loops using real build/test errors
- safer approval gates for repo-wide and multi-file changes
- stronger support for general creation workflows: web apps, CLIs, APIs, internal tools, and automation

## Security and reliability
- sandbox failures are handled as warnings when the runtime is absent instead of blocking the generated app
- local provider fallback remains cautious and avoids silently hard-coding unreachable backends
- suggestion actions remain explicit and reviewable, reducing confusion during live editing


## Model Lab + benchmark-driven routing
- Added evidence-backed Model Lab and Model Registry for task-specific model selection.
- Added repeatable benchmark cases, compact evidence storage, role profiles, and deterministic evidence routing.
- Added advisory local-model evaluator summaries that cannot override measured eligibility.
- Added Model Lab APIs and frontend panel for registry inspection and benchmark runs.
- Generation can automatically use an evidence-backed generation model when one is eligible; otherwise it preserves the requested model.


## Multi-model orchestration foundation
- Moved Model Lab and Project Hub schemas behind formal versioned migrations.
- Added a persistent project task graph with role-specific model assignments and API endpoints.
- Added fresh-evidence eligibility and executable Python benchmark evidence through the hardened sandbox.
- Wired generation tasks to measured role evidence first, with the existing capability selector as a fallback.
- Added migration CLI and a Task Graph frontend panel.


## Model lifecycle + observability
- Added revision-aware benchmark evidence and stale/eligible lifecycle tracking.
- Added persistent evaluator summaries without allowing evaluator prose to override measured routing eligibility.
- Added optional admin-token protection for registry/benchmark/evaluation mutations.
- Added Project Hub provenance events for task graph creation, assignment, and status changes.
- Added model lifecycle/security tests and observability APIs.


## Benchmark coverage + project controls
- Expanded the safe Model Lab suite across implementation, frontend, API, SQL, container, and Git tasks.
- Added per-project role-specific model preferences with auto-routing or explicit pinned configuration.
- Added project model preference APIs and tests.


## Production execution phase
- Connected selected-model chat calls to the existing provider runtime for retries, concurrency limits, timeouts, and telemetry.
- Added provider runtime observability and Model Lab health APIs.
- Documented production execution controls.


## Production execution queue
- Added a formal v6 migration for durable execution jobs with priority, retry, cancellation, and result state.
- Added a persistent execution queue worker and APIs for queue inspection, cancellation, generic model jobs, and project task execution.
- Task execution uses the task graph's assigned model and records durable task completion/output rather than losing work in process memory.
