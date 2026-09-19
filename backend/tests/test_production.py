from production import readiness
def test_readiness_shape():
    d=readiness()
    assert "checks" in d and "capabilities" in d
