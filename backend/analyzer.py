"""Folder / project analysis and live project monitor intelligence."""

from __future__ import annotations

import re
import time
from typing import Any

import db
from project_index import ProjectIndex


def _file_metrics(content: str, language: str) -> dict[str, Any]:
    lines = content.splitlines()
    non_empty = [l for l in lines if l.strip()]
    comments = 0
    if language == "python":
        comments = sum(1 for l in lines if l.strip().startswith("#"))
        funcs = len(re.findall(r"^\s*(?:async\s+)?def\s+\w+", content, re.M))
        classes = len(re.findall(r"^\s*class\s+\w+", content, re.M))
        imports = len(re.findall(r"^\s*(?:from\s+\S+\s+)?import\s+", content, re.M))
        has_main = 'if __name__ == "__main__"' in content or "if __name__ == '__main__'" in content
        has_types = bool(re.search(r"->\s*\w+|:\s*(?:str|int|list|dict|Optional|Any)", content))
        has_doc = '"""' in content or "'''" in content
        has_try = "try:" in content
        has_test = "test_" in content or "pytest" in content or "unittest" in content
    else:
        funcs = classes = imports = 0
        has_main = has_types = has_doc = has_try = has_test = False
        comments = sum(1 for l in lines if l.strip().startswith("//") or l.strip().startswith("/*"))

    return {
        "lines": len(lines),
        "non_empty": len(non_empty),
        "comments": comments,
        "functions": funcs,
        "classes": classes,
        "imports": imports,
        "has_main": has_main,
        "has_types": has_types,
        "has_doc": has_doc,
        "has_try": has_try,
        "has_test": has_test,
        "comment_ratio": round(comments / max(len(non_empty), 1), 2),
    }



def _make_smart_patch(path, content, idea, language):
    import re as _re
    idea_l = idea.lower()
    code = ""
    title = idea[:80]
    if language == "python":
        if "type" in idea_l or "annotation" in idea_l:
            if "from typing import" not in content and "import typing" not in content:
                code = "from typing import Any, Optional, List, Dict\n" + content
            else:
                code = content
            def_annot = _re.sub(
                r"^(def\s+(\w+)\s*\(([^)]*)\))\s*:",
                r"\1 -> Any:",
                code,
                count=1,
                flags=_re.M,
            )
            if def_annot != code:
                code = def_annot
            title = f"Add types in {path}"
        elif "comment" in idea_l:
            code = "# NOTE: clarify non-obvious logic below\n" + content
            title = f"Add guidance comments in {path}"
        elif "test" in idea_l:
            base = path.rsplit("/", 1)[-1].replace(".py", "")
            test_path = f"tests/test_{base}.py"
            code = f'"""Tests for {path}."""\n# Auto-generated scaffold\ndef test_smoke():\n    assert True\n'
            return {
                "id": f"test-{abs(hash(path)) % 10**8}",
                "title": f"Add tests for {path}",
                "detail": idea,
                "target": "file",
                "path": test_path,
                "code": code,
                "kind": "create",
            }
        elif "docstring" in idea_l or "document" in idea_l:
            m = _re.search(r"^(def\s+\w+.*:)\s*$", content, _re.M)
            if m:
                insert_at = m.end()
                code = content[:insert_at] + '\n    """TODO: document."""' + content[insert_at:]
                title = f"Add docstring in {path}"
            else:
                return None
        elif "try" in idea_l or "error" in idea_l:
            if "try:" in content:
                return None
            code = "import logging\nlogger = logging.getLogger(__name__)\n\n" + content
            title = f"Add logging scaffold in {path}"
        else:
            return None
    elif "comment" in idea_l:
        code = f"/* TODO: {idea} */\n" + content
        title = f"Annotate {path}"
    else:
        return None
    if not code or code == content:
        return None
    return {
        "id": f"fix-{abs(hash(path + idea)) % 10**8}",
        "title": title,
        "detail": idea,
        "target": "file",
        "path": path,
        "code": code,
        "kind": "replace",
    }


def analyze_folder(index: ProjectIndex, project_goal: str = "") -> dict[str, Any]:
    """Deep analysis of every indexed file + project-level recommendations."""
    start = time.perf_counter()
    files = index.list_files()
    file_reports = []
    totals = {
        "lines": 0,
        "functions": 0,
        "classes": 0,
        "with_types": 0,
        "with_docs": 0,
        "with_tests": 0,
        "with_error_handling": 0,
    }

    for f in files:
        full = index.get_file(f["path"]) or {}
        content = full.get("content") or ""
        lang = full.get("language") or f.get("language") or "python"
        m = _file_metrics(content, lang)
        totals["lines"] += m["lines"]
        totals["functions"] += m["functions"]
        totals["classes"] += m["classes"]
        if m["has_types"]:
            totals["with_types"] += 1
        if m["has_doc"]:
            totals["with_docs"] += 1
        if m["has_test"]:
            totals["with_tests"] += 1
        if m["has_try"]:
            totals["with_error_handling"] += 1

        issues = []
        ideas = []
        if m["lines"] > 300:
            issues.append("File is large – consider splitting into modules")
        if m["functions"] > 0 and not m["has_types"] and lang == "python":
            issues.append("Missing type hints on functions")
            ideas.append("Add return and parameter type annotations")
        if m["classes"] > 0 and not m["has_doc"]:
            issues.append("Classes lack docstrings")
            ideas.append("Document public classes and methods")
        if m["functions"] > 3 and not m["has_try"]:
            ideas.append("Add try/except around external or model calls")
        if not m["has_test"] and (m["functions"] > 0 or m["classes"] > 0):
            ideas.append("Add unit tests for core functions")
        if m["comment_ratio"] < 0.05 and m["lines"] > 40:
            ideas.append("Increase brief comments for non-obvious logic")
        if m["imports"] > 15:
            issues.append("Many imports – possible tight coupling")
            ideas.append("Group imports and check for unused ones")

        file_reports.append(
            {
                "path": f["path"],
                "language": lang,
                "metrics": m,
                "issues": issues,
                "ideas": ideas,
                "score": max(20, 100 - len(issues) * 12 - (0 if m["has_types"] else 8)),
            }
        )

    # Project-level suggestions guided by goal
    goal = (project_goal or "").strip()
    project_ideas = []
    if goal:
        project_ideas.append(
            {
                "title": "Align structure with project goal",
                "detail": f'Goal: "{goal[:200]}". Ensure modules map cleanly to this outcome.',
            }
        )
    if totals["with_types"] < len(files) * 0.5 and files:
        project_ideas.append(
            {
                "title": "Roll out type hints project-wide",
                "detail": f"Only {totals['with_types']}/{len(files)} files use types – improves IDE help and AI context.",
            }
        )
    if totals["with_tests"] == 0 and files:
        project_ideas.append(
            {
                "title": "Introduce a tests/ package",
                "detail": "No test markers found. Start with one test per core module.",
            }
        )
    if totals["with_docs"] < len(files) * 0.4 and files:
        project_ideas.append(
            {
                "title": "Document public APIs",
                "detail": "Few files have docstrings – helps both humans and AI assistants.",
            }
        )
    if len(files) >= 2:
        project_ideas.append(
            {
                "title": "Keep a single entrypoint",
                "detail": "Expose one clear main/CLI so Run and AI tools know where to start.",
            }
        )
    project_ideas.append(
        {
            "title": "Cache repeated AI prompts",
            "detail": "Identical contexts should hit the suggestion cache to cut latency.",
        }
    )
    project_ideas.append(
        {
            "title": "Separate adapters from core logic",
            "detail": "Model providers (Ollama/HF/API) behind one interface keeps the app portable.",
        }
    )

    # Overall health
    n = max(len(files), 1)
    health = int(
        55
        + (totals["with_types"] / n) * 15
        + (totals["with_docs"] / n) * 10
        + (totals["with_error_handling"] / n) * 10
        + min(10, totals["with_tests"] * 5)
    )
    health = min(98, health)

    # Actionable live recommendations (user can apply)
    actions = []
    for fr in file_reports:
        path = fr["path"]
        full = index.get_file(path) or {}
        content = full.get("content") or ""
        for idea in fr.get("ideas") or []:
            patch = _make_smart_patch(path, content, idea, full.get("language") or "python")
            if patch:
                actions.append(patch)
        for issue in fr.get("issues") or []:
            patch = _make_smart_patch(path, content, issue, full.get("language") or "python")
            if patch and patch["id"] not in {a["id"] for a in actions}:
                actions.append(patch)
    for idea in project_ideas[:4]:
        actions.append({
            "id": f"proj-{abs(hash(idea['title'])) % 10**8}",
            "title": idea["title"],
            "detail": idea.get("detail") or "",
            "target": "note",
            "path": "",
            "code": "",
            "kind": "project",
        })

    latency = int((time.perf_counter() - start) * 1000)
    return {
        "files_analyzed": len(files),
        "totals": totals,
        "file_reports": file_reports,
        "project_ideas": project_ideas,
        "project_goal": goal,
        "health": health,
        "latency_ms": latency,
        "actions": actions,
        "summary": (
            f"Analyzed {len(files)} files · {totals['lines']} lines · "
            f"{totals['functions']} functions · {totals['classes']} classes · health {health}%"
        ),
    }


def monitor_insights(index: ProjectIndex, project_goal: str = "") -> list[dict[str, str]]:
    """Lightweight proactive tips for the live monitor panel."""
    stats = index.stats()
    ideas = []
    if stats.get("files", 0) == 0:
        ideas.append(
            {
                "icon": "📂",
                "title": "Index is empty",
                "detail": "Open or watch a folder so the monitor can reason about your code.",
            }
        )
    else:
        ideas.append(
            {
                "icon": "📊",
                "title": f"{stats.get('files', 0)} files · {stats.get('symbols', 0)} symbols",
                "detail": "Index is live. Run Folder Analysis for deep recommendations.",
            }
        )
    if project_goal:
        ideas.append(
            {
                "icon": "🎯",
                "title": "Project goal set",
                "detail": project_goal[:160] + ("…" if len(project_goal) > 160 else ""),
            }
        )
    else:
        ideas.append(
            {
                "icon": "✏️",
                "title": "Set a project goal",
                "detail": "Tell DreamCoder what this repo is for – all AI replies will stay on track.",
            }
        )
    ideas.append(
        {
            "icon": "💡",
            "title": "Try Ask All",
            "detail": "Compare Llama, Qwen, DeepSeek and Mistral suggestions side by side.",
        }
    )
    ideas.append(
        {
            "icon": "≋",
            "title": "Stream a completion",
            "detail": "Use Stream for token-by-token output you can insert at the cursor.",
        }
    )
    return ideas


def chat_reply(
    message: str,
    index: ProjectIndex,
    project_goal: str = "",
    history: list[dict] | None = None,
    mode: str = "project",
) -> dict[str, Any]:
    """Project-aware or general chat reply (smart heuristic; swap for real LLM later)."""
    start = time.perf_counter()
    msg = (message or "").strip()
    lower = msg.lower()
    stats = index.stats()
    files = index.list_files()
    goal = (project_goal or "").strip()
    is_general = (mode or "project").lower() == "general"

    # Intent routing
    if is_general and not any(k in lower for k in ("analyze", "this project", "this codebase", "my code", "this repo")):
        content = (
            f"General mode — answering freely.\n\n"
            f"You asked: “{msg[:400]}”\n\n"
        )
        # Lightweight general knowledge-style replies
        if any(k in lower for k in ("async", "await", "coroutine")):
            content += (
                "async/await lets you write concurrent code that looks sequential.\n"
                "• `async def` defines a coroutine.\n"
                "• `await` pauses until an awaitable finishes without blocking the event loop.\n"
                "• Use it for I/O (network, disk, APIs), not heavy CPU work.\n\n"
                "Example:\n"
                "```python\n"
                "async def fetch(url):\n"
                "    async with httpx.AsyncClient() as client:\n"
                "        r = await client.get(url)\n"
                "        return r.text\n"
                "```"
            )
        elif any(k in lower for k in ("package", "structure", "project layout", "folder structure")):
            content += (
                "Clean Python package layout:\n"
                "```\n"
                "myapp/\n"
                "  pyproject.toml\n"
                "  README.md\n"
                "  src/myapp/\n"
                "    __init__.py\n"
                "    main.py\n"
                "    ...\n"
                "  tests/\n"
                "```\n"
                "Keep business logic separate from adapters (API, DB, AI models)."
            )
        elif any(k in lower for k in ("hello", "hi ", "hey", "how are you")):
            content += "Hey — I'm the DreamCoder assistant. Ask me anything: coding, project ideas, or general questions."
        else:
            content += (
                "Here's a practical take:\n"
                "1. Clarify the outcome you want in one sentence.\n"
                "2. Break the work into the smallest testable step.\n"
                "3. Implement, run, and iterate.\n\n"
                "If this relates to your open project, switch the chat toggle to **Project** "
                "for answers grounded in your indexed files and goal.\n\n"
                "You can also ask coding concepts, architecture, tooling, or career/process questions here."
            )
        return {
            "role": "assistant",
            "content": content,
            "kind": "general",
            "latency_ms": int((time.perf_counter() - start) * 1000),
        }

    if any(k in lower for k in ("analyze", "analysis", "review folder", "folder analysis", "improve project")):
        analysis = analyze_folder(index, goal)
        top_ideas = analysis["project_ideas"][:4]
        body = analysis["summary"] + "\n\nTop recommendations:\n"
        for i, idea in enumerate(top_ideas, 1):
            body += f"{i}. {idea['title']} — {idea['detail']}\n"
        return {
            "role": "assistant",
            "content": body,
            "kind": "analysis",
            "analysis": analysis,
            "latency_ms": int((time.perf_counter() - start) * 1000),
        }

    if any(k in lower for k in ("what is this", "what does this project", "goal", "purpose", "about this")):
        if goal:
            content = f"Project goal:\n{goal}\n\nIndexed: {stats.get('files', 0)} files, {stats.get('symbols', 0)} symbols."
        else:
            content = (
                "No project goal is set yet. Add one in the Project Context box so every answer "
                "stays aligned with what you're building.\n\n"
                f"Currently indexed: {stats.get('files', 0)} files, {stats.get('symbols', 0)} symbols."
            )
        if files:
            content += "\n\nFiles:\n" + "\n".join(f" · {f['path']}" for f in files[:12])
        return {"role": "assistant", "content": content, "kind": "context", "latency_ms": int((time.perf_counter() - start) * 1000)}

    if any(k in lower for k in ("symbol", "function", "class", "where is", "find ")):
        # crude extract query token
        q = re.sub(r"[^a-zA-Z0-9_]", " ", msg).split()
        q = [t for t in q if len(t) > 2 and t.lower() not in ("where", "find", "the", "function", "class", "symbol")]
        query = q[0] if q else ""
        hits = index.search(query, limit=10) if query else []
        if hits:
            lines = [f"Found {len(hits)} symbol(s) for “{query}”:"]
            for h in hits:
                lines.append(f" · {h.kind} {h.name} — {h.file}:{h.line}")
            content = "\n".join(lines)
        else:
            content = f"No symbols matched “{query or msg}”. Try a shorter name, or index more files."
        return {"role": "assistant", "content": content, "kind": "search", "latency_ms": int((time.perf_counter() - start) * 1000)}

    if any(k in lower for k in ("idea", "suggest", "next step", "what should", "improve", "help me", "analy", "review", "what is", "explain", "update", "cnc", "script", "codebase", "project")):
        analysis = analyze_folder(index, goal)
        lines = []
        lines.append("## Project analysis")
        if goal:
            lines.append(f"**Goal:** {goal}")
        lines.append(analysis.get("summary", ""))
        lines.append("")
        lines.append("## What this codebase is")
        # Sample real file contents for detailed notes
        for f in files[:10]:
            full = index.get_file(f["path"]) or {}
            content = full.get("content") or ""
            lang = full.get("language") or f.get("language") or "text"
            preview = content.strip().splitlines()[:12]
            lines.append(f"### `{f['path']}` ({lang}, {len(content.splitlines())} lines)")
            if preview:
                # describe heuristically
                blob = content.lower()
                role = []
                if "socket" in blob or "bind(" in blob or "listen(" in blob:
                    role.append("networking / socket server or client")
                if "orbit" in blob or "cnc" in blob or "gcode" in blob or "axis" in blob:
                    role.append("CNC / motion / orbit-related logic")
                if "main(" in blob or "__main__" in blob:
                    role.append("entrypoint")
                if "class " in content:
                    role.append("defines types/classes")
                if not role:
                    role.append("supporting module")
                lines.append("- Role: " + ", ".join(role))
                # first non-empty lines as summary
                snippet = " ".join(l.strip() for l in preview if l.strip())[:180]
                if snippet:
                    lines.append(f"- Opens with: `{snippet}…`" if len(snippet) == 180 else f"- Opens with: `{snippet}`")
            fr = next((r for r in analysis.get("file_reports") or [] if r["path"] == f["path"]), None)
            if fr:
                for iss in (fr.get("issues") or [])[:2]:
                    lines.append(f"- Issue: {iss}")
                for idea in (fr.get("ideas") or [])[:2]:
                    lines.append(f"- Improve: {idea}")
            lines.append("")

        lines.append("## Recommended updates (priority)")
        for i, idea in enumerate(analysis.get("project_ideas") or [][:6], 1):
            lines.append(f"{i}. **{idea['title']}** — {idea.get('detail','')}")

        actions = analysis.get("actions") or []
        return {
            "role": "assistant",
            "content": "\n".join(lines),
            "kind": "deep-analysis",
            "analysis": analysis,
            "actions": actions,
            "latency_ms": int((time.perf_counter() - start) * 1000),
        }

    # General / coding advice grounded in project
    content = (
        f"You asked: “{msg[:300]}”\n\n"
        f"Project context: {goal or '(no goal set yet – add one for better answers)'}\n"
        f"Index: {stats.get('files', 0)} files · {stats.get('symbols', 0)} symbols.\n\n"
    )
    if files:
        content += "Relevant files in scope:\n" + "\n".join(f" · {f['path']}" for f in files[:8]) + "\n\n"
    content += (
        "Practical guidance:\n"
        "1. Keep changes small and testable.\n"
        "2. Prefer typed, documented public functions so AI tools stay accurate.\n"
        "3. Use Ask All when you want multiple model opinions.\n"
        "4. Run Folder Analysis after larger refactors.\n"
        "5. Set a clear project goal so every suggestion stays aligned.\n\n"
        "Ask me to analyze the folder, find a symbol, or propose next steps anytime."
    )
    return {
        "role": "assistant",
        "content": content,
        "kind": "general",
        "latency_ms": int((time.perf_counter() - start) * 1000),
    }
