# DreamCoder — change log

## Latest updates
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
