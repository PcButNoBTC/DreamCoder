from __future__ import annotations

import os
import re
from typing import Any

import httpx

from endpoint_validator import fetch_models, rank_models, validate_host


DEFAULT_CENSYS_OLLAMA_QUERY = 'services.software.product:"Ollama" and port:11434'
DEFAULT_PUBLIC_OLLAMA_QUERY = '"Ollama" "11434" "/api/tags"'


def _censys_credentials() -> tuple[str, str]:
    api_id = (os.getenv("CENSYS_API_ID") or "").strip()
    api_secret = (os.getenv("CENSYS_API_SECRET") or "").strip()
    if not api_id or not api_secret:
        raise ValueError(
            "Censys discovery is not configured. Set CENSYS_API_ID and CENSYS_API_SECRET before querying public hosts."
        )
    return api_id, api_secret


def _as_ollama_url(candidate: str) -> str | None:
    if not candidate:
        return None
    cleaned = candidate.strip().rstrip("/")
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        if ":11434" in cleaned:
            return cleaned if cleaned.endswith(":11434") else cleaned
        return f"{cleaned}:11434" if cleaned.count(":") == 0 else cleaned
    return f"http://{cleaned}:11434" if ":11434" not in cleaned else f"http://{cleaned}"


async def query_search_engine_ollama_hosts(
    query: str = DEFAULT_PUBLIC_OLLAMA_QUERY,
    page: int = 1,
    per_page: int = 10,
) -> list[str]:
    """Use a public search engine when no API key is available for Censys."""
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 20))
    encoded = "https://duckduckgo.com/html/?q=" + __import__("urllib.parse").parse.quote(query)

    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get(encoded)
        if resp.status_code >= 400:
            raise ValueError(f"Public search fallback failed ({resp.status_code})")
        text = resp.text

    hosts: list[str] = []
    seen: set[str] = set()
    for match in re.findall(r"https?://[^\s\"'<>]+:11434", text, flags=re.IGNORECASE):
        normalized = match.rstrip("/")
        if normalized not in seen:
            seen.add(normalized)
            hosts.append(normalized)

    # Some pages expose bare hosts without scheme; include them as http://host:11434.
    for raw in re.findall(r"(?:\d{1,3}\.){3}\d{1,3}:11434|(?:[a-z0-9.-]+\.[a-z0-9.-]+):11434", text, flags=re.IGNORECASE):
        candidate = _as_ollama_url(raw)
        if candidate and candidate not in seen:
            seen.add(candidate)
            hosts.append(candidate)

    return hosts[:per_page]


async def query_censys_ollama_hosts(
    query: str = DEFAULT_CENSYS_OLLAMA_QUERY,
    page: int = 1,
    per_page: int = 10,
) -> list[str]:
    """Query Censys for Ollama hosts and return candidate URLs."""
    api_id, api_secret = _censys_credentials()
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 100))
    url = "https://search.censys.io/api/v2/hosts/search"

    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.post(
            url,
            auth=(api_id, api_secret),
            json={"q": query, "page": page, "per_page": per_page},
        )
        if resp.status_code >= 400:
            raise ValueError(f"Censys query failed ({resp.status_code}): {resp.text[:500]}")
        payload = resp.json()

    hits = payload.get("result", {}).get("hits", [])
    hosts: list[str] = []
    seen: set[str] = set()

    for hit in hits:
        ip = (hit.get("ip") or hit.get("ip_address") or "").strip()
        if not ip:
            continue
        candidate = f"http://{ip}:11434"
        if candidate not in seen:
            seen.add(candidate)
            hosts.append(candidate)

    return hosts


async def query_public_ollama_hosts(
    query: str = DEFAULT_CENSYS_OLLAMA_QUERY,
    page: int = 1,
    per_page: int = 10,
) -> list[str]:
    """Prefer Censys when configured, but fall back to public search when no API key is present."""
    try:
        _censys_credentials()
    except ValueError:
        return await query_search_engine_ollama_hosts(query=DEFAULT_PUBLIC_OLLAMA_QUERY if query == DEFAULT_CENSYS_OLLAMA_QUERY else query, page=page, per_page=per_page)
    return await query_censys_ollama_hosts(query=query, page=page, per_page=per_page)


async def validate_ollama_hosts(hosts: list[str], timeout: float = 10.0) -> list[dict[str, Any]]:
    """Validate each host by checking /api/tags, then keep only working Ollama endpoints."""
    validated: list[dict[str, Any]] = []

    for host in hosts:
        try:
            normalized = validate_host(host)
        except ValueError as exc:
            validated.append({"url": host, "status": "invalid", "error": str(exc)})
            continue

        try:
            models = await fetch_models(normalized, timeout=timeout)
            ranked = rank_models(models)
            recommended = ranked[0] if ranked else None
            validated.append(
                {
                    "url": normalized,
                    "status": "ready",
                    "model_count": len(models),
                    "models": ranked,
                    "recommended_model": recommended.get("name") if recommended else None,
                    "available_models": [item.get("name") for item in ranked],
                }
            )
        except ValueError as exc:
            validated.append({"url": normalized, "status": "unreachable", "error": str(exc)})

    return validated


async def discover_working_ollama_models(
    query: str = DEFAULT_CENSYS_OLLAMA_QUERY,
    page: int = 1,
    per_page: int = 10,
    max_hosts: int = 10,
) -> dict[str, Any]:
    """Look up public Ollama hosts and return only those that answer on /api/tags."""
    hosts = await query_public_ollama_hosts(query=query, page=page, per_page=per_page)
    discovered = []
    for candidate in hosts[: max_hosts]:
        discovered.append({"candidate_url": candidate})

    validated = await validate_ollama_hosts([host for host in hosts[:max_hosts]])
    return {
        "ok": True,
        "query": query,
        "candidate_count": len(hosts),
        "validated_count": len(validated),
        "discovered": discovered,
        "hosts": validated,
    }
