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
