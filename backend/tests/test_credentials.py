import credentials


def test_no_keyring_backend_is_handled_gracefully():
    assert credentials.get_secret("github_oauth_token") == ""
    assert credentials.has_secret("github_oauth_token") is False
    assert credentials.available() in (True, False)
