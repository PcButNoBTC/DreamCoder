from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ToolName = Literal["read_file", "search", "write_file", "apply_patch", "run", "test", "git_status", "git_diff"]

@dataclass
class AgentRequest:
    goal: str
    cwd: str
    model: str = "Llama-3.1-8B-Instruct"
    max_repairs: int = 2
    auto_apply: bool = False
    timeout: int = 60

@dataclass
class PlanStep:
    id: str
    title: str
    purpose: str
    tools: list[ToolName] = field(default_factory=list)
    requires_approval: bool = False

@dataclass
class ToolCall:
    id: str
    tool: ToolName
    args: dict[str, Any]
    status: str = "pending"
    output: Any = None
    error: str | None = None

@dataclass
class AgentRun:
    id: str
    status: str
    goal: str
    cwd: str
    model: str = ""
    plan: list[PlanStep] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    repair_count: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
