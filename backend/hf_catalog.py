"""Hugging Face model catalog – fetch, organize, and cache open models."""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

# Curated high-signal open models (always available even offline)
CURATED = [
    {
        "id": "meta-llama/Llama-3.1-8B-Instruct",
        "name": "Llama-3.1-8B-Instruct",
        "author": "meta-llama",
        "task": "text-generation",
        "tags": ["instruct", "llama", "open"],
        "category": "open-instruct",
        "likes": 5000,
        "downloads": 2_000_000,
        "source": "curated",
    },
    {
        "id": "meta-llama/Llama-3.2-3B-Instruct",
        "name": "Llama-3.2-3B-Instruct",
        "author": "meta-llama",
        "task": "text-generation",
        "tags": ["instruct", "llama", "small"],
        "category": "open-instruct",
        "likes": 2000,
        "downloads": 800_000,
        "source": "curated",
    },
    {
        "id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "name": "Qwen2.5-Coder-7B-Instruct",
        "author": "Qwen",
        "task": "text-generation",
        "tags": ["code", "instruct", "qwen"],
        "category": "code",
        "likes": 3000,
        "downloads": 1_500_000,
        "source": "curated",
    },
    {
        "id": "Qwen/Qwen2.5-7B-Instruct",
        "name": "Qwen2.5-7B-Instruct",
        "author": "Qwen",
        "task": "text-generation",
        "tags": ["instruct", "qwen"],
        "category": "open-instruct",
        "likes": 4000,
        "downloads": 2_000_000,
        "source": "curated",
    },
    {
        "id": "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
        "name": "DeepSeek-Coder-V2-Lite-Instruct",
        "author": "deepseek-ai",
        "task": "text-generation",
        "tags": ["code", "instruct", "deepseek"],
        "category": "code",
        "likes": 2500,
        "downloads": 900_000,
        "source": "curated",
    },
    {
        "id": "bigcode/starcoder2-15b",
        "name": "StarCoder2-15B",
        "author": "bigcode",
        "task": "text-generation",
        "tags": ["code", "starcoder"],
        "category": "code",
        "likes": 1800,
        "downloads": 700_000,
        "source": "curated",
    },
    {
        "id": "mistralai/Mistral-7B-Instruct-v0.3",
        "name": "Mistral-7B-Instruct-v0.3",
        "author": "mistralai",
        "task": "text-generation",
        "tags": ["instruct", "mistral", "open"],
        "category": "open-instruct",
        "likes": 6000,
        "downloads": 3_000_000,
        "source": "curated",
    },
    {
        "id": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "name": "Mixtral-8x7B-Instruct",
        "author": "mistralai",
        "task": "text-generation",
        "tags": ["instruct", "moe", "mistral"],
        "category": "open-instruct",
        "likes": 7000,
        "downloads": 2_500_000,
        "source": "curated",
    },
    {
        "id": "google/gemma-2-9b-it",
        "name": "Gemma-2-9B-IT",
        "author": "google",
        "task": "text-generation",
        "tags": ["instruct", "gemma"],
        "category": "open-instruct",
        "likes": 3500,
        "downloads": 1_200_000,
        "source": "curated",
    },
    {
        "id": "microsoft/Phi-3.5-mini-instruct",
        "name": "Phi-3.5-mini-instruct",
        "author": "microsoft",
        "task": "text-generation",
        "tags": ["instruct", "small", "phi"],
        "category": "small",
        "likes": 2200,
        "downloads": 1_000_000,
        "source": "curated",
    },
    {
        "id": "01-ai/Yi-1.5-9B-Chat",
        "name": "Yi-1.5-9B-Chat",
        "author": "01-ai",
        "task": "text-generation",
        "tags": ["chat", "yi", "open"],
        "category": "open-instruct",
        "likes": 1500,
        "downloads": 500_000,
        "source": "curated",
    },
    {
        "id": "HuggingFaceH4/zephyr-7b-beta",
        "name": "Zephyr-7B-Beta",
        "author": "HuggingFaceH4",
        "task": "text-generation",
        "tags": ["instruct", "zephyr", "open"],
        "category": "open-instruct",
        "likes": 4500,
        "downloads": 1_800_000,
        "source": "curated",
    },
    {
        "id": "codellama/CodeLlama-7b-Instruct-hf",
        "name": "CodeLlama-7B-Instruct",
        "author": "codellama",
        "task": "text-generation",
        "tags": ["code", "llama", "instruct"],
        "category": "code",
        "likes": 2800,
        "downloads": 1_100_000,
        "source": "curated",
    },
    {
        "id": "Salesforce/codegen-350M-mono",
        "name": "CodeGen-350M-mono",
        "author": "Salesforce",
        "task": "text-generation",
        "tags": ["code", "small"],
        "category": "code",
        "likes": 800,
        "downloads": 400_000,
        "source": "curated",
    },
    {
        "id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "name": "TinyLlama-1.1B-Chat",
        "author": "TinyLlama",
        "task": "text-generation",
        "tags": ["small", "chat", "llama"],
        "category": "small",
        "likes": 3000,
        "downloads": 2_000_000,
        "source": "curated",
    },
]

_cache: dict[str, Any] = {"ts": 0, "models": [], "organized": {}}
CACHE_TTL = 3600  # 1 hour


def _categorize(model: dict) -> str:
    tags = [t.lower() for t in (model.get("tags") or [])]
    name = (model.get("id") or model.get("name") or "").lower()
    if any(t in tags or t in name for t in ("code", "coder", "starcoder", "codegen", "codellama")):
        return "code"
    if any(t in tags or t in name for t in ("uncensored", "dolphin", "wizard")):
        return "less-restricted"
    if any(t in tags or t in name for t in ("1b", "3b", "mini", "tiny", "small")):
        return "small"
    if any(t in tags or t in name for t in ("instruct", "chat", "it")):
        return "open-instruct"
    return "other"


def _normalize(raw: dict) -> dict:
    mid = raw.get("id") or raw.get("modelId") or ""
    tags = raw.get("tags") or []
    return {
        "id": mid,
        "name": mid.split("/")[-1] if "/" in mid else mid,
        "author": mid.split("/")[0] if "/" in mid else "",
        "task": (raw.get("pipeline_tag") or "text-generation"),
        "tags": tags[:12],
        "category": _categorize({"id": mid, "tags": tags}),
        "likes": raw.get("likes") or 0,
        "downloads": raw.get("downloads") or 0,
        "source": "huggingface",
    }


async def fetch_hf_models(
    search: str = "",
    limit: int = 40,
    filter_task: str = "text-generation",
) -> list[dict]:
    """Query Hugging Face public models API."""
    params: dict[str, Any] = {
        "limit": min(limit, 100),
        "sort": "downloads",
        "direction": -1,
        "filter": filter_task,
    }
    if search:
        params["search"] = search

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get("https://huggingface.co/api/models", params=params)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list):
                return []
            return [_normalize(m) for m in data if m.get("id")]
    except Exception:
        return []


async def get_catalog(force_refresh: bool = False, search: str = "") -> dict[str, Any]:
    """Return organized catalog: curated + live HF results."""
    now = time.time()
    if not force_refresh and not search and _cache["models"] and now - _cache["ts"] < CACHE_TTL:
        return {
            "models": _cache["models"],
            "organized": _cache["organized"],
            "cached": True,
            "updated_at": _cache["ts"],
        }

    live: list[dict] = []
    # Popular code + instruct searches
    queries = [search] if search else ["code instruct", "llama instruct", "mistral instruct"]
    for q in queries:
        batch = await fetch_hf_models(search=q, limit=25)
        live.extend(batch)

    # Dedupe by id, curated first
    seen = set()
    merged: list[dict] = []
    for m in CURATED + live:
        mid = m["id"]
        if mid in seen:
            continue
        seen.add(mid)
        merged.append(m)

    organized: dict[str, list] = {
        "code": [],
        "open-instruct": [],
        "less-restricted": [],
        "small": [],
        "other": [],
    }
    for m in merged:
        cat = m.get("category") or "other"
        if cat not in organized:
            organized[cat] = []
        organized[cat].append(m)

    if not search:
        _cache["ts"] = now
        _cache["models"] = merged
        _cache["organized"] = organized

    return {
        "models": merged,
        "organized": organized,
        "cached": False,
        "updated_at": now,
        "total": len(merged),
        "source": "huggingface.co/api/models + curated open list",
    }


def search_local(query: str, catalog: list[dict], limit: int = 30) -> list[dict]:
    q = query.lower().strip()
    if not q:
        return catalog[:limit]
    scored = []
    for m in catalog:
        blob = f"{m.get('id','')} {m.get('name','')} {' '.join(m.get('tags') or [])}".lower()
        if q in blob:
            scored.append(m)
    return scored[:limit]
