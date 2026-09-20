# DreamCoder roadmap: from AI helper to creation engine

## Vision

DreamCoder should become a practical AI creation platform for software and project work. Instead of only answering a single prompt, it should help a person turn intent into a working project by understanding the repository, choosing the right model, generating useful outputs, validating them, and iterating safely.

## Core principles

- Understand the actual project before changing it
- Match the model to the task, not one model to everything
- Prefer review and approval over silent action
- Validate generated code with real build/test flows
- Keep rollback checkpoints for every meaningful change
- Preserve project context across sessions and refinements

## Phase 1: project understanding

- full-folder indexing and symbol awareness
- architecture summaries and recommendation generation
- project goals and session memory
- better detection of patterns across files and folders

## Phase 2: creation loop

- goal-driven project generation from natural language
- tech stack and architecture recommendations
- template and scaffold generation for web apps, APIs, CLIs, tools, and dashboards
- live suggestion bubbles with Apply / Preview / Ignore control

## Phase 3: validation and repair

- compiler and runtime checks for generated output
- repair loops using real errors
- test generation and project validation
- automatic rollback on failed changes

## Phase 4: agentic execution

- multi-step task planning across files and folders
- agent-style review of proposed changes
- model-ranking and specialist routing per job
- safe GitHub and workspace sync after human approval

## Phase 5: memory and orchestration

- persistent project memory
- task history and model performance tracking
- reuse of working patterns across similar tasks
- ranking of best model per type of work

## Phase 6: broad creation support

DreamCoder should eventually support creation across:

- web apps
- backend services
- internal tools
- automation pipelines
- data dashboards
- scripts and CLIs
- experiments and prototypes
- learning and interactive tools

## Success metric

The project becomes “perfect for creation of anything” when a user can describe an outcome and the system can reliably:

1. understand the current workspace
2. propose a realistic solution
3. generate the needed structure and code
4. validate it
5. repair problems
6. keep the user in control of approvals and final decisions

This is the path from assistant to creation system.
