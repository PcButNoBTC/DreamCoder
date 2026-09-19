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


def test_project_index_clear(tmp_path):
    from project_index import ProjectIndex
    idx = ProjectIndex()
    idx.index_file("__test_scope__/one.py", "def one(): pass")
    assert any(f["path"] == "__test_scope__/one.py" for f in idx.list_files())
    idx.clear()
    assert not idx.list_files()
