# DreamCoder — Next Architecture

## Unified change lifecycle

Every meaningful AI change moves through: **Inspect → Plan → Contract → Patch → Review → Validate → Repair → Approve → Git**.

The durable object is `ChangePlan`. It carries the user goal, workspace, acceptance criteria, task graph, model assignments, upstream artifacts, minimal patches, checkpoint/Git metadata, validation, review and approval state.

## Data-flow task graph

Dependencies are both scheduling and data flow. A completed backend task can emit an API contract; a database task can emit a schema contract; a UI task can emit a component contract. Dependent tasks receive only the artifacts they need plus indexed project context.

## Patch-first development

New projects may create complete files. Existing projects should prefer minimal patches with file-version/content preconditions. If a file changes after planning, the patch is rejected and the task is replanned instead of silently overwriting user work.

## Persistent jobs

Long-running generation is a background job with a job ID, durable state, event history and cancellation. Streaming and resumability are the next UI layer.

## Project intelligence

The project graph should index files, symbols, imports, API routes, database models, tests, commands and dependency manifests. Decision memory should store structured architectural choices with affected files and rationale.

## Model intelligence

Routing should combine capabilities, provider readiness, latency, historical success, validation success, repair count, context requirements and cost where available. Model choices should remain explainable.

## Safety boundary

The agent and developer terminal are separate capabilities. Defaults are local-only, workspace-confined operations, restricted agent commands, explicit write approval, opt-in unrestricted/network execution, audit logging and a production CORS allowlist.

## Git boundary

Significant autonomous changes should have a checkpoint, dedicated branch, reviewable diff, validation result and optional PR. User branches must not be silently overwritten.

## Product surface

Primary AI interactions are inline edit/refactor/fix, project map, architecture preview, task graph preview, diff review, test/repair loop and Git/PR review. Chat remains a control surface.

## Health

Project health should be evidence-based: build, tests, types, security, dependency freshness, Git state, coverage and unresolved review findings. A percentage is secondary to the underlying signals.
