"""Ollama adapter – talks to a local Ollama server (http://localhost:11434).

Install Ollama and pull a model, e.g.:
    ollama pull qwen2.5-coder:7b
Then set DREAMCODER_MODEL=ollama:qwen2.5-coder:7b
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import httpx

from .base import BaseModel, ChatContext, ChatResult, CodeContext, InferenceResult, Suggestion


class OllamaModel(BaseModel):
    name = "Ollama"
    supports_streaming = True

    def __init__(
        self,
        model_name: str = "qwen2.5-coder:7b",
        base_url: str = "http://localhost:11434",
        timeout: float = 60.0,
    ):
        self.model_name = model_name
        self.base_url = (os.getenv("OLLAMA_BASE_URL") or base_url).rstrip("/")
        self.timeout = timeout

    async def complete(self, context: CodeContext) -> InferenceResult:
        start = time.perf_counter()
        prompt = self._build_prompt(context)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 512},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data.get("response", "")
        except Exception as exc:
            return InferenceResult(
                suggestions=[],
                latency_ms=int((time.perf_counter() - start) * 1000),
                model=f"Ollama/{self.model_name}",
                cached=False,
                health={"status": "error", "backend": "ollama", "requested": self.model_name, "error": str(exc)},
            )

        suggestions = self._parse_suggestions(raw)
        latency = int((time.perf_counter() - start) * 1000)

        return InferenceResult(
            suggestions=suggestions,
            latency_ms=latency,
            model=f"Ollama/{self.model_name}",
            cached=False,
            architecture_insights=[
                {
                    "icon": "🦙",
                    "title": "Running on Ollama",
                    "detail": f"Model {self.model_name} served locally.",
                }
            ],
            health={"score": 91, "backend": "ollama"},
        )

    async def chat(self, context: ChatContext) -> ChatResult:
        start = time.perf_counter()
        system = (
            "You are the selected DreamCoder coding assistant. Answer the user's request directly. "
            "Do not claim to have changed files or run commands unless the tool system actually did so."
        )
        if context.project_context:
            system += "\\n\\nProject context:\\n" + (context.project_context or "(no project context available)")
            if context.project_goal:
                system += "\\nProject goal: " + context.project_goal
        history = "\\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in context.history[-8:])
        prompt = system + ("\\n\\nConversation:\\n" + history if history else "") + "\\n\\nuser: " + context.message + "\\nassistant:"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model_name, "prompt": prompt, "stream": False,
                          "options": {"temperature": 0.3, "num_predict": 1200}},
                )
                resp.raise_for_status()
                raw = resp.json().get("response", "").strip()
                return ChatResult(content=raw or "(empty model response)", latency_ms=int((time.perf_counter()-start)*1000), model=f"Ollama/{self.model_name}", backend="ollama")
        except Exception as exc:
            return ChatResult(content=f"Selected model Ollama/{self.model_name} is unavailable: {exc}", latency_ms=int((time.perf_counter()-start)*1000), model=f"Ollama/{self.model_name}", backend="ollama", cached=False)

    async def health_check(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                r.raise_for_status()
                models = [m["name"] for m in r.json().get("models", [])]
                return {
                    "status": "ready" if self.model_name in models or any(self.model_name in m for m in models) else "model-missing",
                    "available_models": models,
                    "requested": self.model_name,
                }
        except Exception as exc:
            return {"status": "unreachable", "error": str(exc)}

    def _build_prompt(self, ctx: CodeContext) -> str:
        return f"""You are an expert coding assistant. Analyze the following {ctx.language} code and return 2-4 concrete, actionable improvement suggestions.

Each suggestion must be in this exact JSON format (array of objects):
[
  {{
    "title": "short title",
    "description": "one sentence why",
    "code": "the suggested code snippet",
    "category": "improvement|refactor|performance|architecture"
  }}
]

Code ({ctx.filename}):
```{ctx.language}
{ctx.code}
```

Selection (if any): {ctx.selection or "(none)"}

Respond ONLY with the JSON array, no markdown fences.
"""

    def _parse_suggestions(self, raw: str) -> list[Suggestion]:
        # Try to extract JSON array
        try:
            # Strip possible markdown
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("```", 1)[0]
            data = json.loads(cleaned)
            out = []
            for i, item in enumerate(data[:5]):
                out.append(
                    Suggestion(
                        id=f"ollama-{i}",
                        title=item.get("title", f"Suggestion {i+1}"),
                        description=item.get("description", ""),
                        code=item.get("code", ""),
                        category=item.get("category", "improvement"),
                        confidence=0.85,
                    )
                )
            return out or self._fallback()
        except Exception:
            return self._fallback()

    def _fallback(self) -> list[Suggestion]:
        return [
            Suggestion(
                id="ollama-fb",
                title="Review generated output",
                description="Model response could not be parsed as structured suggestions.",
                code="# Check Ollama logs or prompt formatting",
                category="improvement",
                confidence=0.5,
            )
        ]


    async def stream_chat(self, context: ChatContext):
        import json
        system="You are the DreamCoder coding assistant. Answer directly and never claim tool execution that did not happen."
        if context.project_context: system+="\nProject context:\n"+context.project_context
        history="\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in context.history[-8:])
        prompt=system+("\nConversation:\n"+history if history else "")+"\nuser: "+context.message+"\nassistant:"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST",f"{self.base_url}/api/generate",json={"model":self.model_name,"prompt":prompt,"stream":True,"options":{"temperature":0.3,"num_predict":1200}}) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line: continue
                    data=json.loads(line)
                    if data.get("response"): yield data["response"]
                    if data.get("done"):
                        yield ""
