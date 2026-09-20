import sandbox


def test_sandbox_api_is_explicit():
    assert isinstance(sandbox.available(), bool)


def test_sandbox_fails_closed_without_runtime(monkeypatch):
    monkeypatch.setattr(sandbox.shutil, "which", lambda _: None)
    result = sandbox.run(".", "python -V")
    assert result["ok"] is False
    assert result["sandboxed"] is False
