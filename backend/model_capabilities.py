"""Capability metadata and routing helpers for DreamCoder generation."""

from __future__ import annotations

from typing import Any

BASE_CAPABILITIES = {
    "qwen": {"code-generation", "code-review", "debugging", "frontend", "backend", "testing"},
    "starcoder": {"code-generation", "code-review", "testing"},
    "deepseek": {"code-generation", "reasoning", "debugging", "backend", "testing", "code-review"},
    "codellama": {"code-generation", "code-review", "debugging"},
    "llama": {"reasoning", "planning", "code-review", "integration"},
    "mistral": {"reasoning", "planning"},
    "mixtral": {"reasoning", "planning", "code-review", "integration"},
    "yi": {"reasoning", "code-review"},
    "wizard": {"reasoning", "planning"},
    "local": {"code-generation", "reasoning", "planning", "debugging", "testing", "integration"},
    "ollama": {"code-generation", "reasoning", "planning", "debugging", "testing", "integration"},
    "mock": {"code-generation", "reasoning", "planning", "debugging", "testing", "integration"},
}

ROLE_CAPABILITIES = {
    "frontend": {"frontend", "code-generation"},
    "backend": {"backend", "code-generation"},
    "api": {"backend", "code-generation"},
    "database": {"backend", "reasoning"},
    "tests": {"testing", "code-generation"},
    "debugging": {"debugging", "code-generation"},
    "documentation": {"reasoning"},
    "integration": {"integration", "code-review"},
    "review": {"code-review", "reasoning"},
    "implementation": {"code-generation"},
}

def model_capabilities(model: str, metadata: dict[str, Any] | None = None) -> set[str]:
    value = str(model or "").lower()
    caps = set()
    if metadata:
        caps.update(str(x) for x in metadata.get("capabilities", []) if x)
    for key, values in BASE_CAPABILITIES.items():
        if key in value:
            caps.update(values)
    if "/" in value:
        caps.update({"code-generation", "reasoning"})
    if not caps:
        caps.update({"reasoning", "code-generation"})
    return caps

def score_model(model: dict[str, Any], needed: set[str]) -> int:
    caps = model_capabilities(str(model.get("id") or model.get("name") or ""), model)
    score = len(caps & needed)
    provider = str(model.get("provider") or "").lower()
    if model.get("status") == "ready":
        score += 2
    if provider == "ollama":
        score += 1
    return score

def select_model(models: list[dict[str, Any]], needed: set[str]) -> str:
    if not models:
        return "Local Model"
    ranked = sorted(models, key=lambda m: score_model(m, needed), reverse=True)
    return str(ranked[0].get("id") or ranked[0].get("name") or "Local Model")
