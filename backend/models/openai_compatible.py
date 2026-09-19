"""OpenAI-compatible chat/completions adapter.
Works with OpenAI and local servers exposing the /v1/chat/completions API.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import httpx

from .base import BaseModel, ChatContext, ChatResult, CodeContext, InferenceResult, Suggestion

class OpenAICompatibleModel(BaseModel):
    supports_streaming = False

    def __init__(self, model_name: str, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: float = 90.0):
        self.model_name = model_name
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self.timeout = timeout
        self.name = f"OpenAI-compatible/{model_name}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _chat_completion(self, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json={"model": self.model_name, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False},
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"].get("content", "")).strip()

    async def complete(self, context: CodeContext) -> InferenceResult:
        start = time.perf_counter()
        system = "You are an expert coding assistant. Return ONLY a JSON array of 2-4 concrete suggestions. Each object must contain title, description, code, and category."
        user = f"Language: {context.language}\nFile: {context.filename}\nSelection: {context.selection or '(none)'}\n\nCode:\n```{context.language}\n{context.code}\n```"
        try:
            raw = await self._chat_completion([{"role": "system", "content": system}, {"role": "user", "content": user}], 700, 0.2)
            suggestions = self._parse_suggestions(raw)
            return InferenceResult(suggestions=suggestions, latency_ms=int((time.perf_counter() - start) * 1000), model=f"OpenAI-compatible/{self.model_name}", health={"status": "ready", "backend": "openai-compatible", "base_url": self.base_url})
        except Exception as exc:
            return InferenceResult(suggestions=[], latency_ms=int((time.perf_counter() - start) * 1000), model=f"OpenAI-compatible/{self.model_name}", health={"status": "error", "backend": "openai-compatible", "error": str(exc), "base_url": self.base_url})

    async def chat(self, context: ChatContext) -> ChatResult:
        start = time.perf_counter()
        system = "You are the selected DreamCoder coding assistant. Answer directly and honestly. Do not claim to have changed files or run commands unless DreamCoder actually did so."
        if context.project_context:
            system += f"\n\nProject goal: {context.project_goal}\nProject context:\n{context.project_context}"
        messages = [{"role": "system", "content": system}]
        messages.extend(context.history[-8:])
        messages.append({"role": "user", "content": context.message})
        try:
            raw = await self._chat_completion(messages, 1400, 0.3)
            return ChatResult(content=raw or "(empty model response)", latency_ms=int((time.perf_counter() - start) * 1000), model=f"OpenAI-compatible/{self.model_name}", backend="openai-compatible")
        except Exception as exc:
            return ChatResult(content=f"Selected model {self.model_name} is unavailable: {exc}", latency_ms=int((time.perf_counter() - start) * 1000), model=f"OpenAI-compatible/{self.model_name}", backend="openai-compatible")

    async def health_check(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/models", headers=self._headers())
                response.raise_for_status()
                data = response.json()
                ids = [str(m.get("id")) for m in data.get("data", []) if m.get("id")]
                return {"status": "ready" if self.model_name in ids else "model-missing", "backend": "openai-compatible", "base_url": self.base_url, "requested": self.model_name, "available_models": ids}
        except Exception as exc:
            return {"status": "unreachable", "backend": "openai-compatible", "base_url": self.base_url, "requested": self.model_name, "error": str(exc)}

    @staticmethod
    def _parse_suggestions(raw: str) -> list[Suggestion]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                data = data.get("suggestions", [])
            if not isinstance(data, list):
                return []
            return [
                Suggestion(
                    id=f"openai-{i}",
                    title=str(item.get("title", f"Suggestion {i + 1}")),
                    description=str(item.get("description", "")),
                    code=str(item.get("code", "")),
                    category=str(item.get("category", "improvement")),
                    confidence=0.85,
                )
                for i, item in enumerate(data[:5])
                if isinstance(item, dict)
            ]
        except Exception:
            return []
