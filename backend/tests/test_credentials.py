import credentials


def test_no_keyring_backend_is_handled_gracefully():
    assert credentials.get_secret("github_oauth_token") == ""
    assert credentials.has_secret("github_oauth_token") is False
    assert credentials.available() in (True, False)


def test_status_never_returns_secret_values():
    data = credentials.status()
    assert set(data) == {"available", "github_token", "hf_token"}
    assert all(isinstance(v, bool) for v in data.values())


def test_invalid_credential_name_is_rejected():
    assert credentials.set_secret("../token", "secret")["ok"] is False
