import tempfile
from pathlib import Path
from checkpoints import create,restore

def test_checkpoint_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d); (p/"src").mkdir(); (p/"src"/"main.py").write_text("one")
        cp=create(p,"test"); (p/"src"/"main.py").write_text("two")
        assert restore(p,cp["path"])["ok"]
        assert (p/"src"/"main.py").read_text()=="one"
