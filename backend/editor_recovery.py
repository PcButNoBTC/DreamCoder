from __future__ import annotations
import subprocess,tempfile
from pathlib import Path
def three_way_merge(base,current,incoming):
    with tempfile.TemporaryDirectory() as d:
        p=Path(d); (p/"current").write_text(current); (p/"base").write_text(base); (p/"incoming").write_text(incoming)
        r=subprocess.run(["git","merge-file","-p",str(p/"current"),str(p/"base"),str(p/"incoming")],capture_output=True,text=True)
        return {"ok":r.returncode==0,"conflicts":r.returncode>0,"content":r.stdout,"exit_code":r.returncode,"stderr":r.stderr}
