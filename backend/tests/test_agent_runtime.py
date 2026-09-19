import tempfile
from pathlib import Path

from agent.permissions import PermissionError, command_allowed, workspace_path
from agent.runtime import AgentRuntime
from agent.tools import ToolRegistry

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