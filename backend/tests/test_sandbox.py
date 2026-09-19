from sandbox import available
def test_sandbox_api_is_explicit():
    assert isinstance(available(),bool)
