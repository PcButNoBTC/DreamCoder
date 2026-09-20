import os
from fastapi import HTTPException
from model_api import _admin_guard

class Req:
    def __init__(self, token=""): self.headers={"X-DreamCoder-Admin-Token":token}

def test_model_lab_guard_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DREAMCODER_MODEL_LAB_ADMIN_TOKEN", raising=False)
    _admin_guard(Req())

def test_model_lab_guard_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("DREAMCODER_MODEL_LAB_ADMIN_TOKEN","secret")
    try:
        _admin_guard(Req("wrong"))
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("expected 403")
