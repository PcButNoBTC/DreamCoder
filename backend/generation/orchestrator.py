"""Capability-routed multi-model generation for DreamCoder."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from models.base import ChatContext

FILE_BLOCK_RE = re.compile(r"===FILE:\s*(.+?)===\n(.*?)\n===END===", re.DOTALL)

CAPABILITIES = {
    "Qwen2.5-Coder": {"code-generation", "code-review", "debugging"},
    "StarCoder2": {"code-generation", "code-review"},
    "DeepSeek-Coder": {"code-generation", "reasoning", "debugging"},
    "CodeLlama-34B": {"code-generation", "code-review"},
    "Llama-3.1-8B-Instruct": {"reasoning", "planning", "code-review"},
    "Llama-3.1-70B-Instruct": {"reasoning", "planning", "code-review"},
    "Mistral-7B-Instruct": {"reasoning", "planning"},
    "Mixtral-8x7B": {"reasoning", "planning", "code-review"},
    "Local Model": {"code-generation", "reasoning", "planning", "debugging"},
    "Ollama": {"code-generation", "reasoning", "planning", "debugging"},
    "mock": {"code-generation", "reasoning", "planning", "debugging"},
}

def _json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None

def _files(text: str) -> list[dict[str, str]]:
    result = []
    for match in FILE_BLOCK_RE.finditer(text or ""):
        path = match.group(1).strip().replace("\\", "/")
        if not path or path.startswith("../") or path.startswith("/") or ":" in path.split("/")[0]:
            continue
        result.append({"path": path, "content": match.group(2)})
    return result

def _pick(models: list[dict[str, Any]], needed: set[str], preferred: list[str]) -> str:
    available = [str(m.get("id") or m.get("name") or "") for m in models]
    for name in preferred:
        if name in available and CAPABILITIES.get(name, set()) & needed:
            return name
    ranked = sorted(
        ((len(CAPABILITIES.get(name, set()) & needed), name) for name in available),
        reverse=True,
    )
    return ranked[0][1] if ranked and ranked[0][0] else (available[0] if available else "Local Model")

def _language(prompt: str) -> str:
    text = " " + (prompt or "").lower() + " "
    for needle, value in (
        (" c++ ", "cpp"), (" cpp ", "cpp"), (" c# ", "csharp"),
        (" rust ", "rust"), (" golang ", "go"), (" go ", "go"),
        (" java ", "java"), (" typescript ", "typescript"),
        (" javascript ", "javascript"), (" python ", "python"),
        (" html ", "html"), (" css ", "css"), (" c ", "c"),
    ):
        if needle in text:
            return value
    return "unknown"

async def _chat(router, model: str, prompt: str, mode: str = "analysis"):
    return await router.chat(model, ChatContext(message=prompt, mode=mode), use_cache=False)

async def orchestrate_generation(prompt: str, project_goal: str, router) -> dict[str, Any]:
    started = time.perf_counter()
    catalog = await router.list_models()
    lang = _language(prompt)

    planner = _pick(catalog, {"planning", "reasoning"},
                    ["Llama-3.1-70B-Instruct", "Llama-3.1-8B-Instruct", "Mixtral-8x7B", "Local Model"])
    coder = _pick(catalog, {"code-generation"},
                  ["Qwen2.5-Coder", "DeepSeek-Coder", "StarCoder2", "CodeLlama-34B", "Local Model"])
    reviewer = _pick(catalog, {"code-review", "reasoning"},
                     ["DeepSeek-Coder", "Llama-3.1-70B-Instruct", "Qwen2.5-Coder", "Local Model"])

    plan_prompt = f"""You are DreamCoder's planning model.
Return ONLY JSON with keys summary, language, tasks, acceptance_criteria.
tasks must be objects with id, role, description, depends_on.
Do not write implementation code.

Project goal: {project_goal or "(none)"}
User request: {prompt}
Detected language: {lang}
"""
    try:
        plan_result = await _chat(router, planner, plan_prompt)
        plan = _json(plan_result.content)
    except Exception:
        plan = None

    if not plan:
        plan = {
            "summary": prompt[:200],
            "language": lang,
            "tasks": [{"id": "task-1", "role": "implementation", "description": prompt, "depends_on": []}],
            "acceptance_criteria": ["The generated project implements the requested core behavior."],
        }

    implementation_prompt = f"""You are DreamCoder's implementation specialist.
Return ONLY complete file blocks using:
===FILE: path/to/file.ext===
<complete contents>
===END===

Implement the original request completely enough to run. Include required configuration,
entry points, and tests when appropriate. Do not emit prose outside file blocks.

Original request:
{prompt}

Project goal:
{project_goal or "(none)"}

Plan:
{json.dumps(plan, indent=2)}
"""
    implementation = await _chat(router, coder, implementation_prompt, mode="project")
    files = _files(implementation.content)

    if not files:
        return {
            "ok": False,
            "source": "orchestrator",
            "error": "Implementation model produced no valid file blocks",
            "models": {"planner": planner, "implementer": coder, "reviewer": reviewer},
            "plan": plan,
        }

    bundle = "\n\n".join(
        f"===FILE: {item['path']}===\n{item['content']}\n===END==="
        for item in files
    )
    review_prompt = f"""You are DreamCoder's code-review model.
Return ONLY JSON with keys approved, summary, issues, repair_instructions.
Compare the generated project with the original request and acceptance criteria.

Original request:
{prompt}

Acceptance criteria:
{json.dumps(plan.get("acceptance_criteria", []))}

Generated files:
{bundle[:50000]}
"""
    try:
        review_result = await _chat(router, reviewer, review_prompt)
        review = _json(review_result.content) or {
            "approved": True, "summary": "Reviewer returned no structured findings.",
            "issues": [], "repair_instructions": [],
        }
    except Exception as exc:
        review = {"approved": True, "summary": f"Review unavailable: {exc}", "issues": [], "repair_instructions": []}

    repaired = False
    if not review.get("approved", True) and review.get("repair_instructions"):
        repair_prompt = f"""You are DreamCoder's repair specialist.
Return ONLY complete file blocks. Fix the review findings without removing working behavior.

Original request:
{prompt}

Review:
{json.dumps(review, indent=2)}

Current files:
{bundle[:50000]}
"""
        try:
            repair_result = await _chat(router, coder, repair_prompt, mode="project")
            repaired_files = _files(repair_result.content)
            if repaired_files:
                files = repaired_files
                repaired = True
        except Exception:
            pass

    name = "-".join(re.findall(r"[A-Za-z0-9]+", prompt.lower())[:4]) or "generated-app"
    return {
        "ok": True,
        "source": "orchestrator",
        "name": name,
        "prompt": prompt,
        "goal": project_goal,
        "stack": {"language": plan.get("language") or lang, "kind": "generated", "build": "auto"},
        "files": files,
        "file_count": len(files),
        "summary": f"Multi-model generation produced {len(files)} files for '{name}'",
        "models": {"planner": planner, "implementer": coder, "reviewer": reviewer},
        "pipeline": ["plan", "implement", "review"] + (["repair"] if repaired else []),
        "plan": plan,
        "review": review,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "run_hint": "Build the generated files using the detected project stack.",
        "self_heal_ready": True,
    }
