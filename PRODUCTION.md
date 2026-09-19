# DreamCoder production engineering baseline

This release moves DreamCoder from a feature prototype toward a production control plane. The application now has explicit boundaries for reliability, security, recovery, AI provider operations, project intelligence, desktop lifecycle and release automation.

## Reliability
- GitHub synchronization uses the Git Data API to create one tree and one commit for a change set, then advances the branch without force. A branch-head mismatch is reported as a conflict.
- Watcher events are coalesced before indexing/sync callbacks.
- Checkpoints are ZIP snapshots with a manifest and SHA-256 hashes. Use /api/workspace/checkpoint, /api/workspace/checkpoints, and /api/workspace/checkpoint/restore.
- SQLite uses WAL, foreign keys and synchronous NORMAL.
- Production diagnostics are exposed through /api/production/readiness and /api/production/diagnostics.

## Agent
POST /api/agent/run/verified runs the implementation flow with a checkpoint, project-aware runtime, detected build/test command, verification and bounded repair attempts. The existing approval-based agent remains available.

## AI operations
Provider calls now have bounded retries, timeout control, request tracing through history, latency/success metrics and capability registration. /api/models remains the provider discovery surface.

## Security
Workspace writes reject absolute paths, traversal and symlink targets. Agent command policy remains restricted by default. Secret-like values are redacted from the audit log. Network execution is separately gated by DREAMCODER_AGENT_NETWORK.

## Project intelligence
project_memory.py persists file nodes, Python import edges, architecture notes and agent memory. Use /api/project/graph and /api/project/graph/reindex.

## GitHub authentication
For local development, GITHUB_TOKEN/GH_TOKEN works. A short-lived GitHub App installation token can be supplied through GITHUB_APP_TOKEN; the token never goes to the browser. Production deployments should obtain short-lived installation credentials rather than embedding long-lived credentials.

## Desktop
Electron now uses context isolation, sandboxing, a single-instance lock, a bounded backend startup wait, backend shutdown handling and an updater hook. electron-builder produces Windows NSIS, macOS DMG and Linux AppImage targets.

## CI / release
CI runs Python tests on Windows, macOS and Linux for Python 3.11 and 3.12, checks JavaScript syntax, and smoke-packages Electron. Tagging v* invokes the cross-platform release workflow.

## Final hardening before licensing
1. Real OAuth/GitHub App installation UX rather than environment-token setup.
2. PTY terminal with streaming process control and cross-platform signals.
3. Full Git staging/branch/merge/conflict UX.
4. Persistent editor crash-recovery buffers and external-edit merge UI.
5. Provider-specific streaming adapters and cost/token accounting from provider usage headers.
6. OS credential/keychain storage for provider and GitHub credentials.
7. Full sandbox/container isolation for autonomous untrusted code execution.
8. End-to-end browser tests, load tests, fuzzing and signed release artifacts.
9. Formal database migration runner and rollback-tested migrations.
10. Complete settings/onboarding/project management UX and diagnostics export.

The architecture is intentionally additive: these remaining items can be implemented without replacing the canonical workspace, GitHub sync, AI routing or agent contracts.