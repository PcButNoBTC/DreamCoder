import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from generation.orchestrator import _files, _language, _pick
from model_capabilities import model_capabilities, select_model


def test_language_detection():
    assert _language("Build a C++ desktop app") == "cpp"
    assert _language("Create a Python API") == "python"


def test_file_block_parser_rejects_absolute_paths():
    text = (
        "===FILE: app/main.py===\nprint('ok')\n===END===\n"
        "===FILE: /tmp/escape.py===\nnope\n===END===\n"
    )
    files = _files(text)
    assert [item["path"] for item in files] == ["app/main.py"]


def test_capability_picker_prefers_specialist():
    models = [
        {"id": "Local Model", "provider": "ollama", "status": "ready"},
        {"id": "Qwen2.5-Coder", "provider": "huggingface", "status": "ready"},
        {"id": "Llama-3.1-8B-Instruct", "provider": "huggingface", "status": "ready"},
    ]
    assert _pick(models, {"code-generation"}, ["Qwen2.5-Coder"]) == "Qwen2.5-Coder"


def test_dynamic_provider_capabilities():
    assert "code-generation" in model_capabilities("ollama:qwen2.5-coder")
    assert "reasoning" in model_capabilities("some-org/some-model")


def test_selector_uses_provider_metadata():
    models = [
        {"id": "m1", "provider": "mock", "status": "ready", "capabilities": ["reasoning"]},
        {"id": "m2", "provider": "mock", "status": "ready", "capabilities": ["testing", "code-generation"]},
    ]
    assert select_model(models, {"testing"}) == "m2"
