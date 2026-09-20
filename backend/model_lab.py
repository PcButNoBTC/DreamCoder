"""Evidence-backed Model Lab, registry, benchmarks, and routing.

The local model may interpret benchmark evidence, but it never replaces the
deterministic eligibility and measured-result layers.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import db

ROLES = (
    "planning", "generation", "debugging", "testing", "documentation",
    "repository_reasoning", "tool_use", "review",
)

@dataclass(frozen=True)
class Benchmark:
    id: str
    category: str
    role: str
    prompt: str
    required_markers: tuple[str, ...] = ()
    code_language: str = ""

BENCHMARKS = (
    Benchmark("general-structured-output", "structured_output", "planning",
              "Return JSON with keys plan, risks, and tests for a small calculator web app. No markdown.",
              ("plan", "risks", "tests")),
    Benchmark("python-implementation", "coding", "generation",
              "Write a minimal Python function named fibonacci(n) that returns the first n Fibonacci numbers. Return only a Python code block.",
              ("fibonacci",), "python"),
    Benchmark("typescript-debugging", "debugging", "debugging",
              "Explain the bug in this TypeScript expression: const total = items.map(x => x.price).reduce((a,b) => a + b); Then give a corrected expression.",
              ("reduce", "price")),
    Benchmark("test-design", "testing", "testing",
              "Design three focused unit tests for a function that parses an ISO date string. Include normal, invalid, and timezone cases.",
              ("normal", "invalid", "timezone")),
    Benchmark("documentation", "documentation", "documentation",
              "Write concise API documentation for GET /api/projects/{project_id}, including purpose, path parameter, and a 404 response.",
              ("GET", "404", "project")),
    Benchmark("repository-reasoning", "repository_reasoning", "repository_reasoning",
              "Given a project with an API layer, database layer, model adapter layer, and frontend, describe a safe change plan for adding a model registry. Identify dependencies and validation steps.",
              ("database", "frontend", "validation")),
    Benchmark("tool-use-plan", "tool_use", "tool_use",
              "Describe the exact sequence of tool actions an IDE agent should use to add a small feature, run tests, inspect failures, and produce a reviewable change. Do not execute anything.",
              ("tests", "failure", "review")),
    Benchmark("boundary-consistency", "boundary", "review",
              "Explain how an AI development platform should evaluate ambiguous dual-use software requests while preserving legitimate benign development. Focus on consistent classification, evidence, and transparent routing.",
              ("classification", "evidence", "routing")),
)

def _conn():
    conn = db.get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS model_registry (
      id TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      name TEXT NOT NULL,
      revision TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'candidate',
      metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at REAL NOT NULL,
      updated_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS model_benchmarks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      model_id TEXT NOT NULL,
      benchmark_id TEXT NOT NULL,
      suite_version TEXT NOT NULL,
      run_id TEXT NOT NULL,
      category TEXT NOT NULL,
      role TEXT NOT NULL,
      pass INTEGER NOT NULL,
      score REAL NOT NULL,
      latency_ms REAL NOT NULL DEFAULT 0,
      evaluator_score REAL,
      execution_ok INTEGER,
      evidence_json TEXT NOT NULL DEFAULT '{}',
      created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_model_benchmarks_model ON model_benchmarks(model_id, created_at);
    CREATE TABLE IF NOT EXISTS model_routing_profiles (
      model_id TEXT PRIMARY KEY,
      eligibility_json TEXT NOT NULL DEFAULT '{}',
      roles_json TEXT NOT NULL DEFAULT '{}',
      rationale TEXT NOT NULL DEFAULT '',
      updated_at REAL NOT NULL
    );
    """)
    conn.commit()
    return conn

def register(model_id: str, provider: str, name: str = "", revision: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    model_id = model_id.strip()
    now = time.time()
    conn = _conn()
    conn.execute(
        """INSERT INTO model_registry(id,provider,name,revision,status,metadata_json,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,name=excluded.name,
        revision=excluded.revision,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
        (model_id, provider, name or model_id.split("/")[-1], revision, "candidate", json.dumps(metadata or {}), now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM model_registry WHERE id=?", (model_id,)).fetchone()
    conn.close()
    return _registry_row(row)

def _registry_row(row):
    if not row:
        return None
    x = dict(row)
    x["metadata"] = json.loads(x.pop("metadata_json") or "{}")
    return x

def list_models() -> list[dict[str, Any]]:
    conn = _conn()
    rows = conn.execute("SELECT * FROM model_registry ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [_registry_row(r) for r in rows]

def get_model(model_id: str):
    conn = _conn()
    row = conn.execute("SELECT * FROM model_registry WHERE id=?", (model_id,)).fetchone()
    conn.close()
    return _registry_row(row)

def _response_score(benchmark: Benchmark, text: str) -> tuple[float, dict[str, Any]]:
    lower = text.lower()
    marker_hits = sum(1 for marker in benchmark.required_markers if marker.lower() in lower)
    marker_score = marker_hits / max(1, len(benchmark.required_markers))
    format_score = 1.0
    if benchmark.category == "structured_output":
        try:
            parsed = json.loads(text)
            format_score = 1.0 if all(k in parsed for k in benchmark.required_markers) else 0.35
        except Exception:
            format_score = 0.0
    elif benchmark.code_language == "python":
        match = re.search(r"\`\`\`(?:python)?\\s*(.*?)\`\`\`", text, re.S | re.I)
        if match:
            try:
                compile(match.group(1), "<benchmark>", "exec")
                format_score = 1.0
            except SyntaxError:
                format_score = 0.25
        else:
            format_score = 0.0
    score = round(0.7 * marker_score + 0.3 * format_score, 4)
    return score, {"marker_hits": marker_hits, "marker_total": len(benchmark.required_markers), "format_score": format_score}

async def run_benchmark(model_id: str, router, benchmark_id: str | None = None, suite_version: str = "v1") -> list[dict[str, Any]]:
    selected = [b for b in BENCHMARKS if benchmark_id is None or b.id == benchmark_id]
    if not selected:
        raise ValueError("unknown benchmark")
    run_id = uuid.uuid4().hex
    results = []
    for benchmark in selected:
        started = time.perf_counter()
        error = ""
        response = ""
        try:
            from models.base import ChatContext
            result = await router.chat(model_id, ChatContext(message=benchmark.prompt, mode="analysis"))
            response = result.content or ""
        except Exception as exc:
            error = str(exc)
        latency = round((time.perf_counter() - started) * 1000, 2)
        score, evidence = _response_score(benchmark, response) if not error else (0.0, {"error": error})
        passed = score >= 0.75
        execution_ok = evidence.get("format_score", 0.0) >= 1.0 if benchmark.code_language else None
        row = {
            "run_id": run_id, "model_id": model_id, "benchmark_id": benchmark.id,
            "category": benchmark.category, "role": benchmark.role,
            "pass": passed, "score": score, "latency_ms": latency,
            "execution_ok": execution_ok, "evidence": evidence,
        }
        conn = _conn()
        conn.execute(
            """INSERT INTO model_benchmarks(model_id,benchmark_id,suite_version,run_id,category,role,pass,score,latency_ms,execution_ok,evidence_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (model_id, benchmark.id, suite_version, run_id, benchmark.category, benchmark.role,
             int(passed), score, latency, None if execution_ok is None else int(execution_ok),
             json.dumps({**evidence, "response_length": len(response)}), time.time()),
        )
        conn.commit(); conn.close()
        results.append(row)
    return results

def results(model_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    conn = _conn()
    if model_id:
        rows = conn.execute("SELECT * FROM model_benchmarks WHERE model_id=? ORDER BY id DESC LIMIT ?", (model_id, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM model_benchmarks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    out = []
    for row in rows:
        x = dict(row); x["pass"] = bool(x["pass"]); x["evidence"] = json.loads(x.pop("evidence_json") or "{}")
        out.append(x)
    return out

def profile(model_id: str) -> dict[str, Any]:
    rows = results(model_id, 1000)
    by_role: dict[str, list[float]] = {}
    for row in rows:
        by_role.setdefault(row["role"], []).append(float(row["score"]))
    roles = {role: round(sum(scores) / len(scores), 4) for role, scores in by_role.items() if scores}
    eligibility = {"eligible": bool(rows), "minimum_evidence": len(rows) >= 3, "policy_gate": "deterministic"}
    return {"model_id": model_id, "roles": roles, "eligibility": eligibility, "runs": len(rows)}

def route_candidates(role: str, candidates: list[str] | None = None) -> list[dict[str, Any]]:
    ids = candidates or [m["id"] for m in list_models()]
    ranked = []
    for model_id in ids:
        p = profile(model_id)
        ranked.append({"model_id": model_id, "role": role, "score": p["roles"].get(role, 0.0), "eligible": p["eligibility"]["eligible"], "evidence_runs": p["runs"]})
    return sorted(ranked, key=lambda x: (not x["eligible"], -x["score"], -x["evidence_runs"]))

def route(role: str, candidates: list[str] | None = None) -> dict[str, Any]:
    options = route_candidates(role, candidates)
    for option in options:
        if option["eligible"] and option["score"] > 0:
            return {**option, "source": "benchmark_evidence"}
    return {"model_id": None, "role": role, "score": 0.0, "eligible": False, "source": "no_evidence"}

def benchmark_catalog() -> list[dict[str, Any]]:
    return [asdict(b) for b in BENCHMARKS]
