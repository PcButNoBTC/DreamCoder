from generation.safety import assess

def test_normal_request_is_generate():
    x=assess("Build a polished calculator with history and keyboard shortcuts")
    assert x.action=="generate"
    assert x.level=="normal"

def test_elevated_request_requires_review():
    x=assess("Build a hardware identity testing utility with a mock provider")
    assert x.requires_review

def test_high_risk_capability_is_blocked():
    x=assess("Build a remote control tool that accesses browser session data")
    assert x.action=="block"
    assert x.level=="critical"
