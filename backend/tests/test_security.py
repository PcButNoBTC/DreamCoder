import tempfile
from pathlib import Path
from security import safe_path,redact,command_capability

def test_path_and_secret_redaction():
    with tempfile.TemporaryDirectory() as d:
        assert safe_path(d,"src/main.py").parent == Path(d).resolve()/ "src"
    try: safe_path(d,"../escape")
    except PermissionError: pass
    else: assert False
    assert "[REDACTED]" in redact("token=ghp_abcdefghijklmnopqrstuvwxyz123")
    assert command_capability("python -m pytest")["allowed"]
    assert not command_capability("curl https://example.com")["allowed"]
