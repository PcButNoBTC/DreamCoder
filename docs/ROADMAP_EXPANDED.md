# DreamCoder Expanded Roadmap

## Stabilize
- Keep CI green across the Python/OS matrix.
- Keep frontend syntax and Electron smoke checks mandatory.
- Add regression tests for workspace isolation, API routing and generated patches.
- Remove duplicate FastAPI routes and split oversized modules incrementally.

## Unified engine
- Adopt ChangePlan as the canonical change object.
- Pass upstream task artifacts to dependent tasks.
- Generate minimal patches for existing projects.
- Add architecture and task-graph previews.
- Add persistent generation jobs, streaming events, cancellation and resume.

## Project intelligence
- Expand the index to imports, routes, database models, tests and dependency manifests.
- Add decision memory with affected files and rationale.
- Build a clickable project map.

## Model intelligence
- Record provider/model latency, failures, validation success and repair count.
- Add health-aware routing and cooldowns.
- Use historical task performance in model selection.
- Keep model choice explainable in the UI.

## Autonomous development
- Inspect → plan → patch → test → repair.
- Checkpoint before application.
- Use agent branches for significant changes.
- Require approval before risky writes or merges.
- Generate PR descriptions from verified diffs and validation output.

## Product
- Project templates, inline AI actions, evidence-based health, persistent sessions and maintenance mode.
- Better onboarding and release update flow.

## Security
- Localhost-only default.
- Production CORS allowlist.
- Separate terminal from agent permissions.
- Audit sensitive actions.
- Workspace and symlink confinement.
- Explicit network/unrestricted execution controls.

## Testing
- Mock-provider end-to-end generation scenarios.
- Conflict/integration tests.
- Repair-loop tests.
- Patch precondition tests.
- Package-install smoke tests.
