# DreamCoder Model Lab

DreamCoder uses benchmark evidence to select models by task role rather than treating one model as a universal default.

## Architecture

1. **Model Registry** records provider, model ID, revision, metadata, and availability.
2. **Model Lab** runs repeatable benchmark cases across planning, generation, debugging, testing, documentation, repository reasoning, tool-use planning, and boundary consistency.
3. **Objective evidence** comes from structured-output checks, code compilation for the safe Python benchmark, pass/fail results, latency, and repeatability history.
4. **Local evaluator** can summarize structured benchmark profiles. Its output is advisory and cannot override deterministic eligibility or measured results.
5. **Benchmark Router** selects a model for a role only when evidence exists.
6. **Project Hub** records routing decisions and benchmark context as project provenance.

## API

- `GET /api/models/registry`
- `POST /api/models/registry`
- `GET /api/models/benchmarks`
- `POST /api/models/benchmarks/run`
- `GET /api/models/benchmarks/results`
- `GET /api/models/{model_id}/profile`
- `POST /api/models/evaluate`
- `POST /api/models/route`

## Routing rule

The router does not select a model because it is more permissive or because another model declined a request. It selects on demonstrated task fit and eligibility. Boundary evaluation measures consistency and appropriate handling of ambiguous requests; it is not a jailbreak leaderboard.

## Hugging Face models

A Hugging Face model can be registered with its Hub ID and optional revision. The existing provider adapter is then used by the benchmark runner. Model revisions should be re-benchmarked when behavior or weights change.

## Evidence retention

Stored benchmark records include model, benchmark, suite version, run ID, role, score, latency, execution status, and compact evidence metadata. Full model responses are not persisted by the Model Lab database.

## Orchestration task graph

A generated project is represented as a persistent task graph rather than one monolithic model call:

`planning → architecture → requirements → generation → validation → testing → debugging → documentation → review`.

Each task has a role, dependency list, selected model, status, attempts, timestamps, and compact output/error metadata. The role router consults fresh benchmark evidence first and falls back to the existing capability selector when measured evidence is unavailable.

## Evidence freshness

Routing uses benchmark evidence from the last 30 days. A model is not eligible for a role unless it has fresh evidence and at least three fresh benchmark records overall. Benchmark execution records compact evidence only; full model responses are not persisted.

## Executable benchmark evidence

The Python implementation benchmark is syntax-checked and, when a container runtime is available, executed inside the hardened sandbox with networking disabled. Other benchmarks remain structured-output checks. This keeps objective execution evidence separate from evaluator prose.

## Lifecycle

Models move through practical states such as `candidate`, `eligible`, and `stale`. A new revision or materially changed provider configuration should be registered with a new revision and re-benchmarked before routing uses it.

## Production lifecycle and observability

Model registry mutations and benchmark/evaluator execution can be protected with `DREAMCODER_MODEL_LAB_ADMIN_TOKEN`. When configured, mutation requests must send `X-DreamCoder-Admin-Token`.

Benchmark records retain the registered model revision so regressions can be compared across revisions. Evaluator summaries are stored separately from measured evidence and remain advisory.

The observability endpoint exposes registry state, recent benchmark evidence, and evaluator summaries for dashboards and diagnostics.

## Regression and repeatability

Benchmark runs can be repeated (bounded to five repeats per request). DreamCoder exposes repeatability summaries with mean, min/max, and standard deviation, plus revision-grouped regression summaries. Benchmark records retain the registered model revision so behavior changes can be compared without treating a newer revision as automatically better or worse.

## Benchmark coverage

The safe suite now covers structured planning, Python and TypeScript implementation, React/frontend design, API contracts, SQL design, Docker/runtime design, Git workflows, debugging, testing, documentation, repository reasoning, tool-use planning, and boundary consistency.

## Project-level routing controls

Each Project Hub project can keep role-specific routing preferences. `auto` uses measured evidence and the router; `pinned` records an explicit model choice for that project role. Pinned choices are project configuration, not a replacement for benchmark evidence elsewhere.

## Resource controls

Benchmark execution is bounded by `DREAMCODER_MODEL_LAB_CONCURRENCY` (default 2) and `DREAMCODER_MODEL_LAB_TIMEOUT` (default 180 seconds). The benchmark runner uses the existing provider runtime and sandbox limits; networking remains disabled for executable benchmark checks.

## Provider discovery

`POST /api/models/discover` asks the existing AI router for currently available local/Hugging Face/OpenAI-compatible/Ollama models and registers their provider metadata. `GET /api/models/{model_id}/health` checks the selected adapter directly. This keeps registry state connected to the real provider adapters rather than treating registration as proof of availability.
