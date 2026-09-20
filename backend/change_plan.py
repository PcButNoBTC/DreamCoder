"""Canonical change-plan model shared by generation, agent, review, validation and Git workflows.
The ChangePlan is the durable contract for a single requested project change.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import json, time, uuid
from typing import Any, Literal
PlanStatus = Literal["planned","running","awaiting_approval","validating","completed","failed","cancelled"]
@dataclass
class ChangeArtifact:
    kind: str
    name: str
    data: dict[str, Any] = field(default_factory=dict)
@dataclass
class ChangePatch:
    path: str
    operation: Literal["create","modify","delete"] = "modify"
    patch: str = ""
    summary: str = ""
    risk: str = "low"
@dataclass
class ChangeTask:
    id: str
    role: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"
    model: str = ""
    artifacts: list[ChangeArtifact] = field(default_factory=list)
    patches: list[ChangePatch] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
@dataclass
class ChangePlan:
    goal: str
    workspace: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: PlanStatus = "planned"
    summary: str = ""
    language: str = "unknown"
    risk: str = "medium"
    acceptance_criteria: list[str] = field(default_factory=list)
    tasks: list[ChangeTask] = field(default_factory=list)
    patches: list[ChangePatch] = field(default_factory=list)
    artifacts: list[ChangeArtifact] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    review: dict[str, Any] = field(default_factory=dict)
    checkpoint: dict[str, Any] = field(default_factory=dict)
    git: dict[str, Any] = field(default_factory=dict)
    approval_required: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    def touch(self, status: PlanStatus | None = None) -> "ChangePlan":
        if status: self.status = status
        self.updated_at = time.time()
        return self
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChangePlan":
        tasks=[]
        for raw in data.get("tasks",[]):
            tasks.append(ChangeTask(
                id=raw["id"], role=raw.get("role","implementation"),
                description=raw.get("description",""), depends_on=raw.get("depends_on",[]),
                status=raw.get("status","pending"), model=raw.get("model",""),
                artifacts=[ChangeArtifact(**a) for a in raw.get("artifacts",[])],
                patches=[ChangePatch(**p) for p in raw.get("patches",[])],
                validation=raw.get("validation",{})))
        return cls(
            goal=data["goal"], workspace=data["workspace"], id=data.get("id",uuid.uuid4().hex),
            status=data.get("status","planned"), summary=data.get("summary",""),
            language=data.get("language","unknown"), risk=data.get("risk","medium"),
            acceptance_criteria=data.get("acceptance_criteria",[]), tasks=tasks,
            patches=[ChangePatch(**p) for p in data.get("patches",[])],
            artifacts=[ChangeArtifact(**a) for a in data.get("artifacts",[])],
            validation=data.get("validation",{}), review=data.get("review",{}),
            checkpoint=data.get("checkpoint",{}), git=data.get("git",{}),
            approval_required=bool(data.get("approval_required",True)),
            created_at=float(data.get("created_at",time.time())),
            updated_at=float(data.get("updated_at",time.time())))
