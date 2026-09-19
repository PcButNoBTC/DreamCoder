"""Base model interface for all inference backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CodeContext:
    code: str
    language: str = "python"
    selection: str = ""
    filename: str = "main.py"
    cursor_line: int = 1
    cursor_col: int = 1
    project_symbols: list[str] = field(default_factory=list)


@dataclass
class Suggestion:
    id: str
    title: str
    description: str
    code: str
    category: str = "improvement"  # improvement | refactor | performance | architecture
    confidence: float = 0.8


@dataclass
class InferenceResult:
    suggestions: list[Suggestion]
    latency_ms: int
    model: str
    cached: bool = False
    architecture_insights: list[dict] = field(default_factory=list)
    health: dict = field(default_factory=dict)


class BaseModel(ABC):
    """Abstract base for every model adapter (Mock, Ollama, HuggingFace, API)."""

    name: str = "base"
    supports_streaming: bool = False

    @abstractmethod
    async def complete(self, context: CodeContext) -> InferenceResult:
        """Return actionable code suggestions for the given context."""
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Return model readiness info."""
        ...

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "supports_streaming": self.supports_streaming,
            "type": self.__class__.__name__,
        }
