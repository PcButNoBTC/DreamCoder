from production import readiness
from security import audit_store_status, redact


def test_readiness_shape():
    d = readiness()
    assert "checks" in d and "capabilities" in d
    assert "required_checks" in d and "optional_checks" in d
    assert d["ok"] is True


def test_optional_integrations_do_not_make_core_readiness_fail():
    d = readiness()
    assert "ai_config" in d["optional_checks"]
    assert "github_config" in d["optional_checks"]
    assert d["ok"] is True


def test_audit_store_is_private():
    d = audit_store_status()
    assert d["ok"] is True
    assert int(d["mode"], 8) & 0o077 == 0


def test_redacts_common_provider_secrets():
    assert "[REDACTED]" in redact("AKIAIOSFODNN7EXAMPLE")
    assert "[REDACTED]" in redact("-----BEGIN PRIVATE KEY-----\\nsecret\\n-----END PRIVATE KEY-----")
