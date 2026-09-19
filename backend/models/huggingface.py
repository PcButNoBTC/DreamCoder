"""Hugging Face Inference / transformers adapter (stub + light path).

For production you can either:
1. Call the HF Inference API (needs HF_TOKEN)
2. Load a local transformers model (needs GPU + lots of RAM)

This file provides a clean interface; the heavy lifting is left as
optional so the rest of the system stays lightweight.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Optional

from .base import BaseModel, ChatContext, ChatResult, CodeContext, InferenceResult, Suggestion
try:
    from provider_runtime import runtime as provider_runtime
except Exception:
    provider_runtime=None
try:
    from quota_tracker import record_response as _record_quota
except Exception:
    def _record_quota(headers, status): pass


class HuggingFaceModel(BaseModel):
    name = "HuggingFace"
    supports_streaming = False

    def __init__(
        self,
        model_id: str = "meta-llama/Llama-3.1-8B-Instruct",
        use_api: bool = True,
        api_token: Optional[str] = None,
    ):
        self.model_id = model_id
        self.use_api = use_api
        self.api_tokens = self._discover_tokens(api_token)
        self.api_token = self.api_tokens[0] if self.api_tokens else None
        self.proxies = self._discover_proxies()
        self._pipeline = None  # lazy-loaded local pipeline

    @staticmethod
    def _normalize_proxy(value: str) -> Optional[str]:
        clean = value.strip()
        if not clean or clean.startswith("#"):
            return None
        if "://" in clean:
            return clean

        if re.match(r"^(?:\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+|\d{1,3}(?:\.\d{1,3}){3}):\d+$", clean):
            return f"http://{clean}"
        return clean

    @staticmethod
    def _discover_proxies() -> list[str]:
        env_names = (
            "HF_PROXY_LIST",
            "HF_PROXIES",
            "HF_PROXY_POOL",
            "HF_PROXY_IPS",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
        )
        proxies: list[str] = []
        seen: set[str] = set()

        def add_proxy(raw_value: str) -> None:
            normalized = HuggingFaceModel._normalize_proxy(raw_value)
            if not normalized:
                return
            if normalized not in seen:
                proxies.append(normalized)
                seen.add(normalized)

        for env_name in env_names:
            value = os.getenv(env_name, "")
            if not value:
                continue
            for part in re.split(r"[,;\n]+", value):
                add_proxy(part)

        for env_name in ("HF_PROXY_FILE", "PROXY_FILE"):
            proxy_file = os.getenv(env_name, "")
            if proxy_file:
                try:
                    with open(proxy_file, "r", encoding="utf-8") as handle:
                        for line in handle:
                            for part in re.split(r"[,;\n]+", line):
                                add_proxy(part)
                except OSError:
                    pass

        candidates = []
        current = os.getcwd()
        seen_paths: set[str] = set()
        while True:
            for name in ("proxy.txt", "backend/proxy.txt"):
                candidate = os.path.join(current, name)
                if candidate not in seen_paths:
                    seen_paths.add(candidate)
                    candidates.append(candidate)
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        for candidate in (os.path.join(repo_root, "proxy.txt"), os.path.join(repo_root, "backend", "proxy.txt")):
            if candidate not in seen_paths:
                candidates.append(candidate)

        for candidate in candidates:
            try:
                with open(candidate, "r", encoding="utf-8") as handle:
                    for line in handle:
                        for part in re.split(r"[,;\n]+", line):
                            add_proxy(part)
            except OSError:
                continue

        return proxies

    def _proxy_for_request(self, index: int = 0) -> Optional[str]:
        if not self.proxies:
            return None
        return self.proxies[index % len(self.proxies)]

    @staticmethod
    def _discover_tokens(api_token: Optional[str] = None) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()

        def add(value: Optional[str]) -> None:
            if not value:
                return
            cleaned = value.strip()
            if cleaned and cleaned not in seen:
                tokens.append(cleaned)
                seen.add(cleaned)

        if api_token:
            add(api_token)
        add(os.getenv("HF_TOKEN"))

        for env_name in sorted(os.environ):
            if env_name.startswith("HF_TOKEN_"):
                add(os.environ.get(env_name))

        for env_name in ("HF_TOKENS", "HF_TOKEN_POOL", "HF_TOKEN_LIST"):
            raw = os.getenv(env_name, "")
            for part in re.split(r"[,;\n]+", raw):
                add(part)

        return tokens

    async def _call_with_fallback(self, *, request_name: str, fn, **kwargs):
        errors: list[str] = []
        for token_index, token in enumerate(self.api_tokens):
            try:
                proxy = self._proxy_for_request(token_index)
                return await fn(token=token, proxy=proxy, **kwargs)
            except Exception as exc:  # pragma: no cover - surfaced in final response
                errors.append(str(exc))
                continue
        if not self.api_tokens:
            raise RuntimeError("No HF tokens are configured. Set HF_TOKEN or HF_TOKEN_1/HF_TOKEN_2 ...")
        raise RuntimeError(f"{request_name} failed across all configured HF tokens: {'; '.join(errors)}")

    async def complete(self, context: CodeContext) -> InferenceResult:
        start = time.perf_counter()

        if self.use_api and self.api_tokens:
            try:
                return await self._call_with_fallback(
                    request_name="Hugging Face completion",
                    fn=self._via_api,
                    context=context,
                    start=start,
                )
            except Exception as exc:
                return InferenceResult(
                    suggestions=[],
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    model=f"HuggingFace/{self.model_id}",
                    cached=False,
                    health={"status": "error", "backend": "huggingface-api", "model_id": self.model_id, "error": str(exc)},
                )
        else:
            return InferenceResult(
                suggestions=[],
                latency_ms=int((time.perf_counter() - start) * 1000),
                model=f"HuggingFace/{self.model_id}",
                cached=False,
                health={"status": "token-missing", "backend": "huggingface", "model_id": self.model_id},
            )

    async def _via_api(self, *, token: str, context: CodeContext, start: float, proxy: Optional[str] = None) -> InferenceResult:
        import httpx

        prompt = self._build_prompt(context)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 400,
                "temperature": 0.2,
                "return_full_text": False,
            },
        }
        client_kwargs = {"timeout": 90.0}
        if proxy:
            client_kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.post(
                    f"https://api-inference.huggingface.co/models/{self.model_id}",
                    headers=headers,
                    json=payload,
                )
                _record_quota(dict(resp.headers), resp.status_code)
                resp.raise_for_status()
                data = resp.json()
                raw = data[0]["generated_text"] if isinstance(data, list) else str(data)
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

        suggestions = [
            Suggestion(
                id="hf-0",
                title="Model suggestion",
                description="Generated by Hugging Face Inference API",
                code=raw[:800],
                category="improvement",
                confidence=0.82,
            )
        ]
        latency = int((time.perf_counter() - start) * 1000)
        return InferenceResult(
            suggestions=suggestions,
            latency_ms=latency,
            model=f"HuggingFace/{self.model_id}",
            cached=False,
            architecture_insights=[
                {
                    "icon": "🤗",
                    "title": "Hugging Face Inference",
                    "detail": f"Using {self.model_id}",
                }
            ],
            health={"score": 88, "backend": "huggingface-api"},
        )

    async def chat(self, context: ChatContext) -> ChatResult:
        start = time.perf_counter()
        prompt = self._build_chat_prompt(context)
        if context.mode == "analysis" or "Return ONLY" in prompt:
            prompt += "\n\nRespond with raw JSON only. No prose, no markdown fences."
        if not self.api_tokens:
            return ChatResult(content=f"Selected model HuggingFace/{self.model_id} has no HF_TOKEN configured.", latency_ms=int((time.perf_counter()-start)*1000), model=f"HuggingFace/{self.model_id}", backend="huggingface")

        errors: list[str] = []
        for token_index, token in enumerate(self.api_tokens):
            try:
                import httpx
                proxy = self._proxy_for_request(token_index)
                client_kwargs = {"timeout": 90.0}
                if proxy:
                    client_kwargs["proxy"] = proxy
                async with httpx.AsyncClient(**client_kwargs) as client:
                    resp = await client.post(
                        f"https://api-inference.huggingface.co/models/{self.model_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"inputs": prompt, "parameters": {"max_new_tokens": 1200, "temperature": 0.3, "return_full_text": False}},
                    )
                    _record_quota(dict(resp.headers), resp.status_code)
                    resp.raise_for_status()
                    data = resp.json()
                    raw = data[0].get("generated_text", "") if isinstance(data, list) else str(data)
                    return ChatResult(content=raw.strip() or "(empty model response)", latency_ms=int((time.perf_counter()-start)*1000), model=f"HuggingFace/{self.model_id}", backend="huggingface")
            except Exception as exc:
                errors.append(str(exc))
                continue

        return ChatResult(content=f"Selected model HuggingFace/{self.model_id} is unavailable across all configured HF tokens: {'; '.join(errors)}", latency_ms=int((time.perf_counter()-start)*1000), model=f"HuggingFace/{self.model_id}", backend="huggingface")

    def _build_chat_prompt(self, context: ChatContext) -> str:
        project = ""
        if context.project_context:
            project = f"\\nProject goal: {context.project_goal}\\nProject context:\\n{context.project_context}\\n"
        history = "\\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in context.history[-8:])
        return f"You are the selected DreamCoder assistant. Answer directly and honestly. Do not claim actions you did not perform.{project}\\nConversation:\\n{history}\\nuser: {context.message}\\nassistant:"

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "configured" if self.api_tokens else "token-missing",
            "model_id": self.model_id,
            "mode": "api" if self.use_api else "local",
            "has_token": bool(self.api_tokens),
            "token_count": len(self.api_tokens),
        }

    def _build_prompt(self, ctx: CodeContext) -> str:
        return (
            f"### Instruction:\n"
            f"Suggest concrete code improvements for the following {ctx.language} snippet.\n"
            f"Return short, actionable suggestions with code.\n\n"
            f"### Code:\n{ctx.code}\n\n"
            f"### Response:\n"
        )


    async def stream_chat(self, context: ChatContext):
        import httpx,json
        prompt=self._build_chat_prompt(context)
        headers={"Authorization":f"Bearer {self.api_token}","Accept":"text/event-stream"}
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST",f"https://api-inference.huggingface.co/models/{self.model_id}",headers=headers,json={"inputs":prompt,"parameters":{"max_new_tokens":1200,"temperature":0.3},"stream":True}) as resp:
                _record_quota(dict(resp.headers),resp.status_code); resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"): continue
                    payload=line[5:].strip()
                    if payload=="[DONE]": break
                    try:
                        data=json.loads(payload)
                        token=data.get("token",{}).get("text") if isinstance(data,dict) else None
                        if token:
                            if provider_runtime: provider_runtime.record_usage("huggingface:"+self.model_id,0,max(1,len(token.split())))
                            yield token
                        elif isinstance(data,dict) and data.get("generated_text"): yield data["generated_text"]
                    except Exception: continue

    def _build_chat_prompt(self, context: ChatContext):
        return "You are the DreamCoder coding assistant. Answer directly.\n"+context.message
