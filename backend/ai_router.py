"""Central AI orchestrator.

Chooses the correct model adapter, applies caching, and enriches
the request with project-index context.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from cache import SuggestionCache
from hf_catalog import CURATED, get_catalog
from models import (
    BaseModel,
    ChatContext,
    ChatResult,
    CodeContext,
    HuggingFaceModel,
    InferenceResult,
    MockModel,
    OllamaModel,
    OpenAICompatibleModel,
)
from project_index import ProjectIndex
from provider_runtime import runtime as provider_runtime


# Display name → adapter factory
# Mock is used by default so the UI works immediately.
# Point any entry at OllamaModel / HuggingFaceModel when you want real weights.
MODEL_REGISTRY = {
    # Code-specialized
    "Qwen2.5-Coder": lambda: MockModel("Qwen2.5-Coder"),
    "StarCoder2": lambda: MockModel("StarCoder2"),
    "DeepSeek-Coder": lambda: MockModel("DeepSeek-Coder"),
    "CodeLlama-34B": lambda: MockModel("CodeLlama-34B"),
    # Open / general (less restricted)
    "Llama-3.1-8B-Instruct": lambda: MockModel("Llama-3.1-8B-Instruct"),
    "Llama-3.1-70B-Instruct": lambda: MockModel("Llama-3.1-70B-Instruct"),
    "Mistral-7B-Instruct": lambda: MockModel("Mistral-7B-Instruct"),
    "Mixtral-8x7B": lambda: MockModel("Mixtral-8x7B"),
    "Yi-34B-Chat": lambda: MockModel("Yi-34B-Chat"),
    "Dolphin-Llama3": lambda: MockModel("Dolphin-Llama3"),
    "WizardLM-2": lambda: MockModel("WizardLM-2"),
    # Local backends
    "Local Model": lambda: _make_local(),
    "Ollama": lambda: OllamaModel(os.getenv("OLLAMA_MODEL", "llama3.1:8b")),
    # Explicit low-level keys
    "ollama": lambda: OllamaModel(os.getenv("OLLAMA_MODEL", "llama3.1:8b")),
    "huggingface": lambda: HuggingFaceModel(model_id=os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")),
    "mock": lambda: MockModel("Mock / offline"),
}


def _configured_ollama_base() -> Optional[str]:
    """Return the configured Ollama base URL only when the user explicitly set one."""
    value = (os.getenv("OLLAMA_BASE_URL") or os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL") or "").strip()
    return value or None


def _ollama_server_available(base_url: str | None = None) -> bool:
    """Return True when a local Ollama endpoint is actually responding."""
    candidates: list[str] = []
    if base_url:
        candidates.append(base_url.rstrip("/"))
    explicit = _configured_ollama_base()
    if explicit:
        candidates.append(explicit.rstrip("/"))
    for candidate in ("http://localhost:11434", "http://127.0.0.1:11434"):
        if candidate not in candidates:
            candidates.append(candidate)

    for url in candidates:
        try:
            response = httpx.get(f"{url}/api/tags", timeout=2.0)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("models"), list):
                return True
        except Exception:
            continue
    return False


def _effective_local_backend() -> str:
    """Pick the default local backend without forcing a dead Ollama install."""
    backend = (os.getenv("DREAMCODER_LOCAL_BACKEND") or "").strip().lower()
    if backend:
        return backend
    if _configured_ollama_base():
        return "ollama"
    if _ollama_server_available():
        return "ollama"
    if HuggingFaceModel._discover_tokens():
        return "huggingface"
    return "mock"


def _make_local() -> BaseModel:
    """Prefer a real local provider. Fall back to HF when no Ollama backend is configured."""
    backend = _effective_local_backend()
    if backend == "ollama":
        return OllamaModel(os.getenv("OLLAMA_MODEL", "tinyllama"), base_url=os.getenv("OLLAMA_BASE_URL") or os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL") or "http://localhost:11434")
    if backend == "huggingface":
        return HuggingFaceModel(model_id=os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct"))
    return MockModel("Local Model (mock)")


def _local_format_markers() -> tuple[str, ...]:
    """Return known local-format markers that should never be sent to the public HF Inference API."""
    return (
        "gguf",
        "ggml",
        "mlx",
        "awq",
        "gptq",
        "marlin",
        "exl2",
        "q4_",
        "q5_",
        "q8_",
        "quantized",
        "int4",
        "int8",
        "fp8",
    )


def _looks_like_local_format_model(name: str) -> bool:
    """True when the selected model is a local compiled or quantized format rather than a normal HF API endpoint."""
    model = (name or "").strip().lower()
    if not model:
        return False
    return any(marker in model for marker in _local_format_markers())


def _canonical_model_id(name: str) -> str:
    """Normalize model strings like 'hf:...' or 'HuggingFace/...' down to the raw model id."""
    value = (name or "").strip()
    if value.startswith("hf:"):
        return value.split(":", 1)[1]
    if value.lower().startswith("huggingface/"):
        return value.split("/", 1)[1]
    if value.startswith("ollama:"):
        return value.split(":", 1)[1]
    if value.startswith("openai:"):
        return value.split(":", 1)[1]
    return value


def _local_ollama_model_for(name: str) -> Optional[OllamaModel]:
    """Respect a configured local Ollama backend even when the UI selected a different model string."""
    if not (os.getenv("OLLAMA_BASE_URL") or os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL")):
        return None

    local_backend = (os.getenv("DREAMCODER_LOCAL_BACKEND") or "ollama").lower()
    if local_backend != "ollama":
        return None

    ollama_model = (
        os.getenv("OLLAMA_MODEL")
        or os.getenv("DREAMCODER_OLLAMA_PRIMARY_MODEL")
        or os.getenv("DREAMCODER_OLLAMA_LOCAL_MODEL")
        or "tinyllama"
    )
    if not name or name == "mock":
        return None

    if name in {"ollama", "Ollama", "Local Model"}:
        return OllamaModel(ollama_model, base_url=os.getenv("OLLAMA_BASE_URL") or os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL"))

    normalized = name.strip().lower()
    model_name = ollama_model.strip().lower()
    if normalized in {model_name, f"ollama:{model_name}", f"ollama:{model_name}:latest"}:
        return OllamaModel(ollama_model, base_url=os.getenv("OLLAMA_BASE_URL") or os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL"))
    if normalized.endswith(f"/{model_name}") or normalized.endswith(f"/{model_name}:latest"):
        return OllamaModel(ollama_model, base_url=os.getenv("OLLAMA_BASE_URL") or os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL"))
    return OllamaModel(ollama_model, base_url=os.getenv("OLLAMA_BASE_URL") or os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL"))


class AIRouter:
    def __init__(self):
        self.cache = SuggestionCache(max_size=256, ttl_seconds=600)
        self.index = ProjectIndex()
        self._models: dict[str, BaseModel] = {}

    def get_model(self, name: str) -> BaseModel:
        """Resolve the selected model to a real provider whenever one is configured.

        Hugging Face catalog IDs such as meta-llama/... are provider model IDs,
        not mock display names. Unknown real IDs must not silently become Mock.
        """
        name = (name or "").strip()
        if name in self._models:
            return self._models[name]

        if name.startswith("ollama:"):
            self._models[name] = OllamaModel(name.split(":", 1)[1])
            return self._models[name]
        if name.startswith("hf:"):
            model_id = name.split(":", 1)[1]
            use_api = not _looks_like_local_format_model(model_id)
            self._models[name] = HuggingFaceModel(model_id=model_id, use_api=use_api)
            return self._models[name]
        if name.lower().startswith("huggingface/"):
            model_id = name.split("/", 1)[1]
            use_api = not _looks_like_local_format_model(model_id)
            self._models[name] = HuggingFaceModel(model_id=model_id, use_api=use_api)
            return self._models[name]
        if name.startswith("openai:"):
            self._models[name] = OpenAICompatibleModel(name.split(":", 1)[1])
            return self._models[name]

        ollama_base = _configured_ollama_base()
        ollama_model = (
            os.getenv("OLLAMA_MODEL")
            or os.getenv("DREAMCODER_OLLAMA_PRIMARY_MODEL")
            or os.getenv("DREAMCODER_OLLAMA_LOCAL_MODEL")
            or "tinyllama"
        )
        local_backend = _effective_local_backend()
        has_hf_tokens = bool(HuggingFaceModel._discover_tokens())

        # Local compiled/quantized models such as GGUF or MLX are not valid HF Inference API targets.
        # When such a model is selected, prefer the configured local engine and disable the API route.
        if _looks_like_local_format_model(name):
            if local_backend == "ollama" or ollama_base:
                self._models[name] = OllamaModel(ollama_model, base_url=ollama_base or "http://localhost:11434")
                return self._models[name]
            self._models[name] = HuggingFaceModel(model_id=name, use_api=False)
            return self._models[name]

        # Explicit local Ollama config should win only when the user actually configured it.
        if local_backend == "ollama" and ollama_base and not has_hf_tokens and "/" in name and not name.lower().startswith(("http://", "https://")):
            self._models[name] = OllamaModel(ollama_model, base_url=ollama_base)
            return self._models[name]

        # Full Hub IDs like "TroyDoesAI/Unrestricted-Knowledge-Will-Not-Refuse-15B"
        # are real Hugging Face models, not mock placeholders. Resolve them to HF even
        # when no explicit token is present so the app does not silently hide a real model.
        if "/" in name and not name.lower().startswith(("http://", "https://")):
            self._models[name] = HuggingFaceModel(model_id=name)
            return self._models[name]

        if ollama_base and (
            name in {"ollama", "Ollama", "Local Model"}
            or name == ollama_model
            or name.endswith(f"/{ollama_model}")
            or name.endswith(f"/{ollama_model}:latest")
            or local_backend == "ollama"
        ):
            self._models[name] = OllamaModel(ollama_model, base_url=ollama_base)
            return self._models[name]

        factory = MODEL_REGISTRY.get(name)
        self._models[name] = factory() if factory is not None else MockModel(name)
        return self._models[name]

    async def list_models(self) -> list[dict[str, Any]]:
        """Discover provider-backed models and prefer the configured local route without forcing dead Ollama instances."""
        models: list[dict[str, Any]] = []

        local_backend = _effective_local_backend()
        if local_backend == "ollama":
            ollama_url = os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
            ollama_requested = os.getenv("DREAMCODER_OLLAMA_PRIMARY_MODEL") or os.getenv("OLLAMA_MODEL") or "tinyllama"
            ollama = OllamaModel(ollama_requested, base_url=ollama_url)
            ollama_health = await ollama.health_check()

            if ollama_health.get("status") in {"ready", "model-missing"} or os.getenv("DREAMCODER_LOCAL_BACKEND", "").lower() == "ollama":
                models.append({"id": "Local Model", "name": "Local Model", "provider": "ollama", "status": "ready", "real": True})
                for tag in ollama_health.get("available_models", []):
                    models.append({"id": f"ollama:{tag}", "name": tag, "provider": "ollama", "status": "ready", "real": True})
                if ollama_health.get("status") == "ready" and not any(m["provider"] == "ollama" for m in models):
                    models.append({"id": f"ollama:{ollama_requested}", "name": ollama_requested, "provider": "ollama", "status": "ready", "real": True})
        elif local_backend == "huggingface":
            models.append({"id": "Local Model", "name": "Local Model", "provider": "huggingface", "status": "ready", "real": True})

        hf_tokens = [
            os.getenv("HF_TOKEN"),
            *[os.getenv(f"HF_TOKEN_{i}") for i in range(1, 25)],
        ]
        if any(token and token.strip() for token in hf_tokens):
            try:
                catalog = await get_catalog()
                for model in catalog.get("models", [])[:80]:
                    model_id = model.get("id") or model.get("name")
                    if not model_id:
                        continue
                    entry = {
                        "id": f"hf:{model_id}",
                        "name": model.get("name") or model_id,
                        "provider": "huggingface",
                        "status": "ready",
                        "real": True,
                    }
                    if not any(existing["id"] == entry["id"] for existing in models):
                        models.append(entry)
            except Exception:
                pass

            hf_id = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
            health = await HuggingFaceModel(model_id=hf_id).health_check()
            if not any(m["id"] == f"hf:{hf_id}" for m in models):
                models.append({"id": f"hf:{hf_id}", "name": hf_id, "provider": "huggingface", "status": health.get("status", "configured"), "real": True})

        openai_model = os.getenv("OPENAI_MODEL", "")
        if openai_model and (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL")):
            provider = OpenAICompatibleModel(openai_model)
            health = await provider.health_check()
            ids = health.get("available_models") or [openai_model]
            for mid in ids:
                models.append({"id": f"openai:{mid}", "name": mid, "provider": "openai-compatible", "status": "ready", "real": True})

        if not models:
            models.append({"id": "mock", "name": "Mock / offline", "provider": "mock", "status": "ready", "real": False})

        return models

    async def suggest(
        self,
        model_name: str,
        context: CodeContext,
        use_cache: bool = True,
    ) -> InferenceResult:
        # Enrich context with project symbols
        context.project_symbols = self.index.to_context_symbols()

        if use_cache:
            cached = self.cache.get(model_name, context)
            if cached is not None:
                return cached

        model = self.get_model(model_name)
        provider = getattr(model, 'backend', None) or model.__class__.__name__
        result = await provider_runtime.call(provider, lambda: model.complete(context), retries=2, timeout=float(os.getenv('DREAMCODER_AI_TIMEOUT','120')))

        if use_cache:
            self.cache.put(model_name, context, result)

        return result

    async def recommend(self, model_name: str, prompt: str, expected_format: str = "json") -> dict[str, Any]:
        from model_race import race, build_lanes_from_env
        lanes=build_lanes_from_env()
        if not lanes:
            return {"ok":False,"error":"No model lanes configured","content":""}
        ctx=ChatContext(message=prompt,mode="analysis")
        result=await race(lanes,ctx,expected_format=expected_format,min_responses=1)
        if not result.winner:
            return {"ok":False,"error":"No usable response from any lane","losers":[{"lane":l.lane.name,"reason":l.reason} for l in result.losers],"content":""}
        return {"ok":True,"content":result.winner.content,"winning_lane":result.winner.lane.name,"model":result.winner.lane.model,"duration_ms":result.duration_ms,"losers":[{"lane":l.lane.name,"reason":l.reason} for l in result.losers]}

    def _chat_fallback_candidates(self, model_name: str) -> list[str]:
        """Return a ranked list of chat-capable fallbacks for a model the provider rejected."""
        current = _canonical_model_id(model_name)
        candidates: list[str] = []

        if _configured_ollama_base() or _ollama_server_available() or (os.getenv("DREAMCODER_LOCAL_BACKEND", "").lower() == "ollama"):
            ollama_model = (
                os.getenv("OLLAMA_MODEL")
                or os.getenv("DREAMCODER_OLLAMA_PRIMARY_MODEL")
                or os.getenv("DREAMCODER_OLLAMA_LOCAL_MODEL")
                or "tinyllama"
            )
            candidates.append(f"ollama:{ollama_model}")
            candidates.append("Local Model")

        for item in CURATED:
            mid = (item.get("id") or "").strip()
            if not mid or mid == current or _looks_like_local_format_model(mid):
                continue
            candidates.append(f"hf:{mid}")

        # Prefer stable chat-capable models before falling back to generic catalog entries.
        preferred = [
            "hf:Qwen/Qwen2.5-Coder-7B-Instruct",
            "hf:meta-llama/Llama-3.1-8B-Instruct",
            "hf:mistralai/Mistral-7B-Instruct-v0.3",
            "hf:deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
        ]
        for item in preferred:
            if _canonical_model_id(item) == current:
                continue
            if item not in candidates:
                candidates.append(item)

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.strip()
            if key and key not in seen:
                seen.add(key)
                deduped.append(key)
        return deduped

    @staticmethod
    def _is_provider_rejection(value: Any) -> bool:
        """True when the model route is known to be refused or unavailable for chat."""
        text = ""
        if isinstance(value, Exception):
            text = str(value)
        elif isinstance(value, ChatResult):
            text = str(value.content or "")
        elif value is not None:
            text = str(value)
        if not text:
            return False
        lowered = text.lower()
        markers = (
            "401 unauthorized",
            "unauthorized",
            "forbidden",
            "not currently available",
            "not supported",
            "unsupported",
            "client error",
            "provider route",
            "refused",
            "model is unavailable",
            "model is not supported",
            "could not load",
        )
        return any(marker in lowered for marker in markers)

    async def _fallback_chat(self, original_name: str, context: ChatContext, reason: Any) -> ChatResult:
        last_error = reason
        for fallback_name in self._chat_fallback_candidates(original_name):
            if fallback_name in {original_name, f"hf:{_canonical_model_id(original_name)}"}:
                continue
            try:
                fallback_model = self.get_model(fallback_name)
                provider = getattr(fallback_model, 'backend', None) or fallback_model.__class__.__name__
                result = await provider_runtime.call(provider, lambda: fallback_model.chat(context), retries=2, timeout=float(os.getenv('DREAMCODER_AI_TIMEOUT','120')))
                if result and not self._is_provider_rejection(result):
                    if result.content and not result.content.startswith("[Fallback from "):
                        result.content = f"[Fallback from {original_name}]\n{result.content}"
                    return result
            except Exception as exc:
                last_error = exc
                continue
        if isinstance(last_error, Exception):
            raise last_error
        raise RuntimeError(str(last_error))

    async def chat(
        self,
        model_name: str,
        context: ChatContext,
        use_cache: bool = False,
    ) -> ChatResult:
        """Send conversational requests to the exact selected model adapter."""
        if os.getenv("DREAMCODER_CHAT_USE_RACE","0").lower() in {"1","true","yes"}:
            from model_race import race, build_lanes_from_env
            lanes=build_lanes_from_env()
            if lanes:
                result=await race(lanes,context,expected_format=None,min_responses=1)
                if result.winner:
                    return ChatResult(content=result.winner.content,latency_ms=result.duration_ms,model=result.winner.lane.model,backend=result.winner.lane.kind)
        if context.mode == "project":
            context.project_context = self._project_context()
        model = self.get_model(model_name)
        provider = getattr(model, 'backend', None) or model.__class__.__name__
        try:
            result = await provider_runtime.call(provider, lambda: model.chat(context), retries=2, timeout=float(os.getenv('DREAMCODER_AI_TIMEOUT','120')))
            if result and self._is_provider_rejection(result):
                return await self._fallback_chat(model_name, context, result)
            return result
        except Exception as exc:
            if self._is_provider_rejection(exc):
                return await self._fallback_chat(model_name, context, exc)
            raise

    def _project_context(self) -> str:
        files = self.index.list_files()
        chunks: list[str] = []
        for f in files[:12]:
            full = self.index.get_file(f["path"]) or {}
            content = (full.get("content") or "")[:1200]
            chunks.append(f"# --- {f['path']} ---\\n{content}")
        return "\\n\\n".join(chunks) or "(project index is empty)"

    async def health(self, model_name: Optional[str] = None) -> dict[str, Any]:
        info: dict[str, Any] = {
            "cache": self.cache.stats(),
            "index": self.index.stats(),
            "available_models": list(MODEL_REGISTRY.keys()),
        }
        if model_name:
            model = self.get_model(model_name)
            info["model"] = await model.health_check()
        return info

    def index_file(self, path: str, content: str, language: str = "python"):
        return self.index.index_file(path, content, language)


    def provider_status(self) -> dict[str,Any]:
        return provider_runtime.snapshot()
