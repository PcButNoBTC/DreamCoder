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


def test_local_model_prefers_live_ollama_before_hf(monkeypatch):
    monkeypatch.delenv("DREAMCODER_LOCAL_BACKEND", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("DREAMCODER_OLLAMA_PRIMARY_URL", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")

    import ai_router

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "qwen2.5-coder:7b"}]}

    monkeypatch.setattr(ai_router.httpx, "get", lambda *args, **kwargs: FakeResp())

    router = AIRouter()
    model = router.get_model("Local Model")

    assert isinstance(model, OllamaModel)
    assert getattr(model, "model_name", "") == "qwen2.5-coder:7b"


def test_local_model_falls_back_to_hf_when_ollama_is_unconfigured(monkeypatch):
    monkeypatch.delenv("DREAMCODER_LOCAL_BACKEND", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("DREAMCODER_OLLAMA_PRIMARY_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")

    import ai_router
    monkeypatch.setattr(ai_router.httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("offline")))

    router = AIRouter()
    model = router.get_model("Local Model")

    assert isinstance(model, HuggingFaceModel)


def test_hf_model_id_falls_back_to_local_ollama_when_no_hf_token(monkeypatch):
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_MODEL", raising=False)
    router = AIRouter()

    model = router.get_model("meta-llama/Llama-3.1-8B-Instruct")

    assert isinstance(model, OllamaModel)
    assert getattr(model, "model_name", "") == "qwen2.5-coder:7b"


def test_hf_repo_model_id_does_not_fall_back_to_mock(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "mock")
    router = AIRouter()

    model = router.get_model("TroyDoesAI/Unrestricted-Knowledge-Will-Not-Refuse-15B")

    assert isinstance(model, HuggingFaceModel)
    assert getattr(model, "model_id", "") == "TroyDoesAI/Unrestricted-Knowledge-Will-Not-Refuse-15B"


def test_local_format_model_ids_are_not_routed_to_hf_api(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "mock")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("DREAMCODER_OLLAMA_PRIMARY_URL", raising=False)

    router = AIRouter()
    model = router.get_model("TheBloke/Llama-3.1-8B-Instruct-GGUF")

    assert isinstance(model, HuggingFaceModel)
    assert getattr(model, "use_api", True) is False


def test_local_format_model_ids_prefer_ollama_when_configured(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

    router = AIRouter()
    model = router.get_model("mlx-community/Qwen2.5-Coder-7B-Instruct-MLX")

    assert isinstance(model, OllamaModel)
    assert getattr(model, "model_name", "") == "qwen2.5-coder:7b"


def test_huggingface_prefixed_model_name_routes_to_hf_adapter(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "mock")

    router = AIRouter()
    model = router.get_model("HuggingFace/deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct")

    assert isinstance(model, HuggingFaceModel)
    assert getattr(model, "model_id", "") == "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"


def test_list_models_prefers_ollama_when_configured(monkeypatch):
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "tinyllama")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    router = AIRouter()
    models = asyncio.run(router.list_models())

    assert models[0]["provider"] == "ollama"
    assert models[0]["id"] == "Local Model"


def test_list_models_includes_hf_catalog_when_token_present(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    monkeypatch.setenv("DREAMCODER_LOCAL_BACKEND", "mock")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    async def fake_get_catalog(force_refresh=False, search=""):
        return {
            "models": [
                {"id": "meta-llama/Llama-3.1-8B-Instruct", "name": "Llama-3.1-8B-Instruct"},
                {"id": "Qwen/Qwen2.5-Coder-7B-Instruct", "name": "Qwen2.5-Coder-7B-Instruct"},
            ]
        }

    import ai_router
    monkeypatch.setattr(ai_router, "get_catalog", fake_get_catalog)

    router = AIRouter()
    models = asyncio.run(router.list_models())

    ids = {m["id"] for m in models}
    assert "hf:meta-llama/Llama-3.1-8B-Instruct" in ids
    assert "hf:Qwen/Qwen2.5-Coder-7B-Instruct" in ids


def test_ollama_model_uses_primary_url_when_configured(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("DREAMCODER_OLLAMA_PRIMARY_URL", "http://185.216.203.106:11434")
    monkeypatch.setenv("DREAMCODER_OLLAMA_PRIMARY_MODEL", "qwen2.5-coder:7b")

    model = OllamaModel("qwen2.5-coder:7b")

    assert model.base_url == "http://185.216.203.106:11434"
    assert model.model_name == "qwen2.5-coder:7b"


def test_public_search_fallback_discovery_without_censys_credentials(monkeypatch):
    monkeypatch.delenv("CENSYS_API_ID", raising=False)
    monkeypatch.delenv("CENSYS_API_SECRET", raising=False)

    class FakeResponse:
        status_code = 200
        text = '<a href="http://8.8.8.8:11434">Ollama</a><a href="http://example.com:11434">Ollama</a>'

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            return FakeResponse()

    import censys
    monkeypatch.setattr(censys.httpx, "AsyncClient", FakeClient)

    hosts = asyncio.run(censys.query_public_ollama_hosts())

    assert "http://8.8.8.8:11434" in hosts
    assert "http://example.com:11434" in hosts
