"""Central AI orchestrator.

Chooses the correct model adapter, applies caching, and enriches
the request with project-index context.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from cache import SuggestionCache
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


def _make_local() -> BaseModel:
    """Prefer Ollama if available, otherwise fall back to mock."""
    backend = os.getenv("DREAMCODER_LOCAL_BACKEND", "mock").lower()
    if backend == "ollama":
        return OllamaModel(os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"))
    if backend == "huggingface":
        return HuggingFaceModel()
    return MockModel("Local Model (mock)")


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
        if name not in self._models:
            if name.startswith("ollama:"):
                self._models[name] = OllamaModel(name.split(":", 1)[1])
            elif name.startswith("hf:"):
                self._models[name] = HuggingFaceModel(model_id=name.split(":", 1)[1])
            elif name.startswith("openai:"):
                self._models[name] = OpenAICompatibleModel(name.split(":", 1)[1])
            elif "/" in name and os.getenv("HF_TOKEN"):
                self._models[name] = HuggingFaceModel(model_id=name)
            else:
                ollama_base = os.getenv("OLLAMA_BASE_URL") or os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL")
                ollama_model = (
                    os.getenv("OLLAMA_MODEL")
                    or os.getenv("DREAMCODER_OLLAMA_PRIMARY_MODEL")
                    or os.getenv("DREAMCODER_OLLAMA_LOCAL_MODEL")
                    or ""
                )
                if ollama_base and (name in {"ollama", "Ollama", "Local Model"} or name == ollama_model or name.endswith(f"/{ollama_model}")):
                    self._models[name] = OllamaModel(ollama_model or "tinyllama", base_url=ollama_base)
                else:
                    factory = MODEL_REGISTRY.get(name)
                    self._models[name] = factory() if factory is not None else MockModel(name)
        return self._models[name]

    async def list_models(self) -> list[dict[str, Any]]:
        """Discover provider-backed models and explicitly label mock mode."""
        models: list[dict[str, Any]] = [
            {"id": "mock", "name": "Mock / offline", "provider": "mock", "status": "ready", "real": False}
        ]

        ollama_url = os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        ollama_requested = os.getenv("DREAMCODER_OLLAMA_PRIMARY_MODEL") or os.getenv("OLLAMA_MODEL") or "llama3.1:8b"
        ollama = OllamaModel(ollama_requested, base_url=ollama_url)
        ollama_health = await ollama.health_check()
        for tag in ollama_health.get("available_models", []):
            models.append({"id": f"ollama:{tag}", "name": tag, "provider": "ollama", "status": "ready", "real": True})
        if ollama_health.get("status") == "ready" and not any(m["provider"] == "ollama" for m in models):
            models.append({"id": f"ollama:{ollama_requested}", "name": ollama_requested, "provider": "ollama", "status": "ready", "real": True})

        if os.getenv("HF_TOKEN"):
            hf_id = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
            health = await HuggingFaceModel(model_id=hf_id).health_check()
            models.append({"id": f"hf:{hf_id}", "name": hf_id, "provider": "huggingface", "status": health.get("status", "configured"), "real": True})

        openai_model = os.getenv("OPENAI_MODEL", "")
        if openai_model and (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL")):
            provider = OpenAICompatibleModel(openai_model)
            health = await provider.health_check()
            ids = health.get("available_models") or [openai_model]
            for mid in ids:
                models.append({"id": f"openai:{mid}", "name": mid, "provider": "openai-compatible", "status": "ready", "real": True})

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
        return await provider_runtime.call(provider, lambda: model.chat(context), retries=2, timeout=float(os.getenv('DREAMCODER_AI_TIMEOUT','120')))

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
