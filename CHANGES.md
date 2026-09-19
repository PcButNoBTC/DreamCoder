# DreamCoder — change log

## Added
- Parallel model racing across configured Ollama and Hugging Face lanes.
- Ollama endpoint validation and model ranking.
- Hugging Face quota tracking.
- ZIP backups on GitHub sync failure and agent command audit logging.
- Agent permission and backup regression tests.

## Changed
- Restricted agent shell execution by default.
- Added change-type tagging and sync warnings.
- Added model recommendation and model-backed project generation.
- Added quota and Ollama endpoint controls to the IDE.

## Security
- Restricted agent commands no longer use shell=True.
- Sync failures preserve generated file contents locally.
- Agent command execution is audited.
