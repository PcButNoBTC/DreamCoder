from __future__ import annotations
import asyncio
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Optional
import httpx
try:
    from models.base import ChatContext
except ImportError:
    from backend.models.base import ChatContext

@dataclass
class Lane:
    name: str
    kind: str
    url: str = ""
    model: str = ""
    timeout: float = 90.0
    weight: int = 1

@dataclass
class LaneResult:
    lane: Lane
    ok: bool
    content: str = ""
    reason: str = ""
    latency_ms: int = 0

@dataclass
class RaceResult:
    winner: Optional[LaneResult]
    losers: list[LaneResult]
    race_id: str
    duration_ms: int
    min_responses_used: int

_REFUSALS = [
    re.compile(r"\bI (cannot|can't|am unable|won't|will not)\b", re.I),
    re.compile(r"\bI('m| am) (not able|unable) to\b", re.I),
    re.compile(r"\bI (must|have to) (decline|refuse)\b", re.I),
    re.compile(r"\bas an AI\b.*\b(cannot|can't|unable)\b", re.I | re.S),
]

def is_usable(text: str, expected_format: str | None = None) -> tuple[bool, str]:
    if text is None or len(text.strip()) < 20:
        return False, "empty"
    stripped = text.strip()
    if any(rx.search(stripped) for rx in _REFUSALS):
        return False, "refused"
    if expected_format == "json":
        cleaned = stripped
        fence = chr(96) * 3
        if cleaned.startswith(fence):
            cleaned = cleaned.split("\n", 1)[-1].rsplit(fence, 1)[0].strip()
        try:
            json.loads(cleaned)
        except Exception:
            return False, "unusable"
    elif expected_format == "file_blocks":
        if not re.search(r"===FILE:\s*.+?===\n.*?\n===END===", stripped, re.S):
            return False, "unusable"
    return True, ""

async def _query_lane(lane: Lane, context: ChatContext, expected_format: str | None = None) -> LaneResult:
    started = time.perf_counter()
    try:
        if lane.kind == "ollama":
            messages = [{"role": "user", "content": context.message}]
            if context.project_context:
                messages.insert(0, {"role": "system", "content": f"Project goal: {context.project_goal}\nProject context:\n{context.project_context}"})
            async with httpx.AsyncClient(timeout=lane.timeout) as client:
                resp = await client.post(lane.url.rstrip("/") + "/api/chat", json={"model": lane.model, "messages": messages, "stream": False})
                resp.raise_for_status()
                data = resp.json()
            content = str((data.get("message") or {}).get("content") or data.get("response") or "")
        elif lane.kind == "hf":
            try:
                from models.huggingface import HuggingFaceModel
            except ImportError:
                from backend.models.huggingface import HuggingFaceModel
            content = (await HuggingFaceModel(model_id=lane.model).chat(context)).content
        else:
            return LaneResult(lane, False, reason="error")
        ok, reason = is_usable(content, expected_format)
        return LaneResult(lane, ok, content, reason, int((time.perf_counter() - started) * 1000))
    except asyncio.CancelledError:
        raise
    except (httpx.TimeoutException, asyncio.TimeoutError):
        return LaneResult(lane, False, reason="timeout", latency_ms=int((time.perf_counter() - started) * 1000))
    except Exception:
        return LaneResult(lane, False, reason="error", latency_ms=int((time.perf_counter() - started) * 1000))

async def race(lanes: list[Lane], context: ChatContext, expected_format: str | None = None,
               min_responses: int = 1, overall_timeout: float = 120.0) -> RaceResult:
    race_id = uuid.uuid4().hex
    started = time.perf_counter()
    if not lanes:
        return RaceResult(None, [], race_id, 0, 0)
    tasks = {asyncio.create_task(_query_lane(lane, context, expected_format)): lane for lane in lanes}
    completed = []
    try:
        iterator = asyncio.as_completed(tasks, timeout=overall_timeout)
        while True:
            try:
                future = next(iterator)
            except StopIteration:
                break
            try:
                result = await future
            except Exception:
                continue
            completed.append(result)
            if len(completed) >= max(1, min(min_responses, len(lanes))):
                break
    except asyncio.TimeoutError:
        pass
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    usable = [r for r in completed if r.ok]
    winner = max(usable, key=lambda r: r.lane.weight) if usable else None
    losers = [r for r in completed if r is not winner]
    for task, lane in tasks.items():
        if task.cancelled() or not task.done():
            losers.append(LaneResult(lane, False, reason="cancelled"))
    return RaceResult(winner, losers, race_id, int((time.perf_counter() - started) * 1000), len(completed))

def build_lanes_from_env() -> list[Lane]:
    specs = [
        ("remote-ollama", "DREAMCODER_OLLAMA_PRIMARY_URL", "DREAMCODER_OLLAMA_PRIMARY_MODEL", 10),
        ("secondary-ollama", "DREAMCODER_OLLAMA_SECONDARY_URL", "DREAMCODER_OLLAMA_SECONDARY_MODEL", 8),
        ("tertiary-ollama", "DREAMCODER_OLLAMA_TERTIARY_URL", "DREAMCODER_OLLAMA_TERTIARY_MODEL", 6),
    ]
    lanes = []
    for name, url_key, model_key, weight in specs:
        url = os.getenv(url_key, "").strip()
        model = os.getenv(model_key, "").strip()
        if url and model:
            lanes.append(Lane(name, "ollama", url, model, 90.0, weight))
    if os.getenv("DREAMCODER_OLLAMA_LOCAL_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
        url = os.getenv("DREAMCODER_OLLAMA_LOCAL_URL", "").strip()
        model = os.getenv("DREAMCODER_OLLAMA_LOCAL_MODEL", "").strip() or os.getenv("OLLAMA_MODEL", "").strip()
        if url and model:
            lanes.append(Lane("local-ollama", "ollama", url, model, 90.0, 5))
    if os.getenv("HF_TOKEN") and os.getenv("DREAMCODER_HF_FALLBACK_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
        model = os.getenv("HF_MODEL", "").strip()
        if model:
            lanes.append(Lane("hf-qwen", "hf", model=model, weight=2))
    model = os.getenv("HF_FALLBACK_MODEL", "").strip()
    if model:
        lanes.append(Lane("hf-dolphin", "hf", model=model, weight=1))
    return sorted(lanes, key=lambda lane: lane.weight, reverse=True)
