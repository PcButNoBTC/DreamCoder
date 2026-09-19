import tempfile
from pathlib import Path

from agent.permissions import PermissionError, command_allowed, workspace_path
from agent.runtime import AgentRuntime
from agent.tools import ToolRegistry
from models import ChatContext, MockModel

def test_workspace_cannot_escape():
    root=tempfile.mkdtemp()
    try:
        workspace_path(root, '../secret')
        assert False
    except PermissionError:
        pass

def test_safe_command_policy():
    assert command_allowed('pytest -q')
    assert command_allowed('git status --short')
    assert not command_allowed('rm -rf .')
    assert not command_allowed('curl https://example.com')

def test_write_requires_approval(tmp_path: Path):
    tools=ToolRegistry(str(tmp_path),auto_apply=False)
    try:
        tools.write_file('x.txt','hello')
        assert False
    except PermissionError:
        pass

def test_read_and_search(tmp_path: Path):
    (tmp_path/'app.py').write_text('def hello():\n    return 1\n',encoding='utf-8')
    tools=ToolRegistry(str(tmp_path),auto_apply=True)
    assert 'hello' in tools.read_file('app.py')['content']
    assert tools.search('hello')['hits'][0]['path']=='app.py'

def test_runtime_constructs():
    assert AgentRuntime() is not None

def test_selected_model_chat_path():
    import asyncio
    result = asyncio.run(MockModel("Dolphin-Llama3").chat(ChatContext(message="hello", mode="general")))
    assert result.model == "Dolphin-Llama3"
    assert result.backend == "mock"
    assert "hello" in result.content


def test_folder_scope_json_parser():
    from analyzer import _extract_json
    parsed = _extract_json('prefix {"project_type":"desktop IDE","recommendations":[]} suffix')
    assert parsed["project_type"] == "desktop IDE"


def test_agent_run_persists_selected_model():
    from agent.types import AgentRun
    run = AgentRun(id="x", status="planning", goal="test", cwd="/tmp", model="mock")
    assert run.to_dict()["model"] == "mock"


def test_openai_compatible_suggestion_parser():
    from models.openai_compatible import OpenAICompatibleModel
    raw = '[{"title":"Add test","description":"Cover the function","code":"assert True","category":"improvement"}]'
    parsed = OpenAICompatibleModel._parse_suggestions(raw)
    assert parsed[0].title == "Add test"


def test_router_uses_explicit_provider_prefixes():
    from ai_router import AIRouter
    from models import OllamaModel, HuggingFaceModel, OpenAICompatibleModel
    router = AIRouter()
    assert isinstance(router.get_model("ollama:test-model"), OllamaModel)
    assert isinstance(router.get_model("hf:test/model"), HuggingFaceModel)
    assert isinstance(router.get_model("openai:test-model"), OpenAICompatibleModel)
