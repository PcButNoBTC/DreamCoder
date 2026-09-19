import tempfile
from pathlib import Path
from project_memory import ProjectMemory

def test_graph_index():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d); (p/"a.py").write_text("import json\n")
        m=ProjectMemory(); result=m.index(d)
        assert result["nodes"] >= 1
        assert any(n["path"]=="a.py" for n in m.graph()["nodes"])
