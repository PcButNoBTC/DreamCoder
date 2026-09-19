import tempfile
from security import safe_path

def test_traversal_variants_are_rejected():
    with tempfile.TemporaryDirectory() as d:
        bad=["../x","../../x","a/../../x","/tmp/x","\\\\server\\share\\x","a/../b"]
        for value in bad:
            try: safe_path(d,value)
            except PermissionError: continue
            assert value=="/never"
