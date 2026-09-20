"""Public generation orchestration API."""

from __future__ import annotations

from model_capabilities import model_capabilities
from generation.engine import generate, parse_files, language_hint

_files = parse_files
_language = language_hint

async def orchestrate_generation(prompt: str, project_goal: str, router):
    return await generate(prompt, project_goal, router)

def _pick(models, needed, preferred=None):
    from model_capabilities import select_model
    return select_model(models, needed)
