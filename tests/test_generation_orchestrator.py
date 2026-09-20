import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from generation.orchestrator import _files, _language, _pick


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
        {"id": "Local Model"},
        {"id": "Qwen2.5-Coder"},
        {"id": "Llama-3.1-8B-Instruct"},
    ]
    assert _pick(models, {"code-generation"}, ["Qwen2.5-Coder"]) == "Qwen2.5-Coder"
