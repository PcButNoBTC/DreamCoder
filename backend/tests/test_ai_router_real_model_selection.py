import asyncio
import os

from ai_router import AIRouter
from models import HuggingFaceModel, OllamaModel


def test_hf_token_pool_uses_presets(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("HF_TOKEN_1", "token-1")
    monkeypatch.setenv("HF_TOKEN_2", "token-2")
    monkeypatch.setenv("HF_PROXY_LIST", "127.0.0.1:8080, 127.0.0.1:8081")

    model = HuggingFaceModel()

    assert model.api_token == "token-1"
    assert model.api_tokens == ["token-1", "token-2"]
    assert model.proxies == ["http://127.0.0.1:8080", "http://127.0.0.1:8081"]


def test_proxy_txt_file_is_supported(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HF_PROXY_LIST", raising=False)
    monkeypatch.delenv("HF_PROXIES", raising=False)
    monkeypatch.delenv("HF_PROXY_POOL", raising=False)
    monkeypatch.delenv("HF_PROXY_IPS", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("ALL_PROXY", raising=False)
    (tmp_path / "proxy.txt").write_text("127.0.0.1:8080\n127.0.0.1:8081\n# comment\n")

    model = HuggingFaceModel()

    assert model.proxies == ["http://127.0.0.1:8080", "http://127.0.0.1:8081"]


def test_selected_model_prefers_configured_local_ollama(monkeypatch):
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "tinyllama")
    router = AIRouter()

    model = router.get_model("Local Model")

    assert isinstance(model, OllamaModel)
    assert getattr(model, "model_name", "") == "tinyllama"


def test_hf_repo_model_id_does_not_fall_back_to_mock(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "mock")
    router = AIRouter()

    model = router.get_model("TroyDoesAI/Unrestricted-Knowledge-Will-Not-Refuse-15B")

    assert isinstance(model, HuggingFaceModel)
    assert getattr(model, "model_id", "") == "TroyDoesAI/Unrestricted-Knowledge-Will-Not-Refuse-15B"


def test_list_models_prefers_ollama_when_configured(monkeypatch):
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "tinyllama")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    router = AIRouter()
    models = asyncio.run(router.list_models())

    assert models[0]["provider"] == "ollama"
    assert models[0]["id"] == "Local Model"
