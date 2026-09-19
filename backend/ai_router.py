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
)
from project_index import ProjectIndex


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
    "huggingface": lambda: HuggingFaceModel(
        model_id=os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    ),
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
        if name not in self._models:
            factory = MODEL_REGISTRY.get(name)
            if factory is not None:
                self._models[name] = factory()
            elif "/" in name:
                # Hugging Face style id → HF adapter (API or mock fallback)
                self._models[name] = HuggingFaceModel(model_id=name)
            else:
                self._models[name] = MockModel(name)
        return self._models[name]

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
        result = await model.complete(context)

        if use_cache:
            self.cache.put(model_name, context, result)

        return result

    async def chat(
        self,
        model_name: str,
        context: ChatContext,
        use_cache: bool = False,
    ) -> ChatResult:
        """Send conversational requests to the exact selected model adapter."""
        if context.mode == "project":
            context.project_context = self._project_context()
        model = self.get_model(model_name)
        return await model.chat(context)

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
