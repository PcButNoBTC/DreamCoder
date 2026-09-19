"""Smart mock model that produces realistic, context-aware suggestions.

This is the default backend so the UI works immediately without
requiring GPU or external services.  Replace with OllamaModel or
HuggingFaceModel when you want real inference.
"""

from __future__ import annotations

import hashlib
import random
import re
import time
from typing import Any

from .base import BaseModel, CodeContext, InferenceResult, Suggestion


class MockModel(BaseModel):
    name = "Mock-Coder"
    supports_streaming = False

    def __init__(self, display_name: str = "Qwen2.5-Coder"):
        self.display_name = display_name

    async def complete(self, context: CodeContext) -> InferenceResult:
        start = time.perf_counter()
        suggestions = self._generate_suggestions(context)
        insights = self._architecture_insights(context)
        health = self._project_health(context)
        latency = int((time.perf_counter() - start) * 1000) + random.randint(80, 320)

        return InferenceResult(
            suggestions=suggestions,
            latency_ms=latency,
            model=self.display_name,
            cached=False,
            architecture_insights=insights,
            health=health,
        )

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "model": self.display_name,
            "backend": "mock",
            "latency_estimate_ms": 180,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_suggestions(self, ctx: CodeContext) -> list[Suggestion]:
        code = ctx.code or ""
        lang = (ctx.language or "python").lower()
        suggestions: list[Suggestion] = []

        # 1. Type / validation suggestions
        if "def " in code and "->" not in code and lang == "python":
            suggestions.append(
                Suggestion(
                    id="s1",
                    title="Add return type annotations",
                    description="Improve readability and enable static analysis.",
                    code="def example(self, value: str) -> list[str]:\n    ...",
                    category="improvement",
                    confidence=0.92,
                )
            )

        if "model" in code.lower() and "validate" not in code.lower():
            suggestions.append(
                Suggestion(
                    id="s2",
                    title="Add input validation",
                    description="Validate model input before execution to avoid runtime errors.",
                    code="# AI suggestion\nif not isinstance(context, CodeContext):\n    raise TypeError('Expected CodeContext')\n",
                    category="improvement",
                    confidence=0.88,
                )
            )

        # 2. Async / concurrency
        if "async def" in code:
            suggestions.append(
                Suggestion(
                    id="s3",
                    title="Keep async boundaries",
                    description="Good foundation for remote inference. Consider adding timeout.",
                    code="async def suggest(self, context: CodeContext, timeout: float = 30.0) -> list[str]:\n    ...",
                    category="architecture",
                    confidence=0.85,
                )
            )
        elif "def suggest" in code or "def complete" in code:
            suggestions.append(
                Suggestion(
                    id="s4",
                    title="Consider making the API async",
                    description="Async enables non-blocking inference calls.",
                    code="async def suggest(self, context: CodeContext) -> list[str]:\n    return await self.model.complete(context)",
                    category="architecture",
                    confidence=0.80,
                )
            )

        # 3. Caching
        if "cache" not in code.lower() and len(code) > 100:
            suggestions.append(
                Suggestion(
                    id="s5",
                    title="Cache repeated prompts",
                    description="Reduce latency for identical context hashes.",
                    code="from functools import lru_cache\n\n@lru_cache(maxsize=128)\ndef _cached_complete(hash_key: str, ...):\n    ...",
                    category="performance",
                    confidence=0.87,
                )
            )

        # 4. Error handling
        if "try:" not in code and ("await" in code or "model" in code.lower()):
            suggestions.append(
                Suggestion(
                    id="s6",
                    title="Add robust error handling",
                    description="Wrap model calls so failures surface cleanly to the UI.",
                    code="try:\n    result = await self.model.complete(context)\nexcept Exception as exc:\n    logger.exception('Inference failed')\n    raise InferenceError(str(exc)) from exc",
                    category="improvement",
                    confidence=0.90,
                )
            )

        # 5. Docstrings / typing
        if '"""' not in code and "class " in code:
            suggestions.append(
                Suggestion(
                    id="s7",
                    title="Add class docstring",
                    description="Document the public interface for future contributors.",
                    code='class DreamCoder:\n    """AI-native coding assistant that routes requests to local or remote models."""\n    ...',
                    category="improvement",
                    confidence=0.75,
                )
            )

        # Fallback if nothing matched
        if not suggestions:
            suggestions = [
                Suggestion(
                    id="s0",
                    title="Extract helper functions",
                    description="Break long methods into smaller, testable units.",
                    code="# AI suggestion\ndef _prepare_context(raw: str) -> CodeContext:\n    return CodeContext(code=raw)\n",
                    category="refactor",
                    confidence=0.70,
                ),
                Suggestion(
                    id="s0b",
                    title="Add logging",
                    description="Structured logs help debug inference latency later.",
                    code="import logging\nlogger = logging.getLogger(__name__)\nlogger.info('Suggestion request received')",
                    category="improvement",
                    confidence=0.72,
                ),
            ]

        # Deterministic ordering + limit
        suggestions = suggestions[:5]
        return suggestions

    def _architecture_insights(self, ctx: CodeContext) -> list[dict]:
        return [
            {
                "icon": "↗",
                "title": "Separate inference adapters",
                "detail": "Keep Hugging Face, Ollama and API providers behind one interface.",
            },
            {
                "icon": "⌘",
                "title": "Add project indexing",
                "detail": "Build a symbol-aware context layer for larger repos.",
            },
            {
                "icon": "⚡",
                "title": "Introduce request queue",
                "detail": "Protect local models from concurrent overload.",
            },
        ]

    def _project_health(self, ctx: CodeContext) -> dict:
        # Simple heuristic based on code length & structure
        lines = len((ctx.code or "").splitlines())
        score = min(98, 60 + lines // 3 + random.randint(0, 15))
        return {
            "score": score,
            "files_indexed": 142 + (hash(ctx.code or "") % 30),
            "symbols": 8421 + (hash(ctx.code or "") % 500),
            "ai_latency_ms": 180 + random.randint(0, 250),
            "open_suggestions": len(self._generate_suggestions(ctx)),
        }
