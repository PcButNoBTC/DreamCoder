"""Container sandbox for autonomous build/test execution. Disabled unless Docker/Podman is available."""
from __future__ import annotations
import os,shutil,subprocess
from pathlib import Path
def available():
    return bool(shutil.which("docker") or shutil.which("podman"))
def run(root:str,command:str,timeout:int=300,network=False):
    engine=shutil.which("docker") or shutil.which("podman")
    if not engine:
        return {"ok":False,"exit_code":-1,"error":"No Docker/Podman sandbox runtime installed","sandboxed":False}
    image=os.getenv("DREAMCODER_SANDBOX_IMAGE","python:3.12-slim")
    root=str(Path(root).resolve())
    args=[engine,"run","--rm","--read-only","--cap-drop=ALL","--security-opt","no-new-privileges","--pids-limit","256","--memory","2g","--cpus","2","-v",root+":/workspace:rw","-w","/workspace"]
    args += ["--network","bridge" if network else "none",image,"sh","-lc",command]
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=max(5,min(timeout,900)))
        return {"ok":p.returncode==0,"exit_code":p.returncode,"stdout":p.stdout,"stderr":p.stderr,"sandboxed":True,"engine":Path(engine).name,"image":image}
    except subprocess.TimeoutExpired as e:
        return {"ok":False,"exit_code":-1,"stdout":e.stdout or "","stderr":e.stderr or "sandbox timeout","sandboxed":True,"timeout":True}
