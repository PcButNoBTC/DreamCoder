# DreamCoder — change log

## Latest updates
- Fixed the default Local Model fallback so it prefers a working backend instead of forcing an unreachable Ollama default.
- Added regression tests covering Ollama-unconfigured and Hugging Face fallback behavior.
- Improved the Windows launchers to detect Ollama, install it automatically when missing, and fall back to Hugging Face instead of blocking startup.
- Updated the static frontend serving instructions and corrected the path mismatch that caused 404s when opening the app.
- Refreshed the project documentation to reflect the actual working state and long-term project potential.

## Added
- Parallel model racing across configured Ollama and Hugging Face lanes.
- Ollama endpoint validation and model ranking.
- Hugging Face quota tracking.
- ZIP backups on GitHub sync failure and agent command audit logging.
- Agent permission and backup regression tests.
- More resilient local startup behavior for users who do not already have Ollama installed.

## Changed
- Restricted agent shell execution by default.
- Added change-type tagging and sync warnings.
- Added model recommendation and model-backed project generation.
- Added quota and Ollama endpoint controls to the IDE.
- Updated project documentation to emphasize the app as a real AI coding workspace, not just a demo shell.

## Security
- Restricted agent commands no longer use shell=True.
- Sync failures preserve generated file contents locally.
- Agent command execution is audited.
- Local fallback logic avoids silently defaulting into unreachable providers.
