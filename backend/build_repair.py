from __future__ import annotations
import json,os,re,subprocess,time
from pathlib import Path
from sandbox import run as sandbox_run, available as sandbox_available

BUILDERS={
 "python":["python -m compileall -q ."],
 "javascript":["npm install --no-audit --no-fund","npm test -- --runInBand"],
 "typescript":["npm install --no-audit --no-fund","npm run build --if-present","npm test -- --runInBand"],
 "rust":["cargo check","cargo test"],
 "go":["go build ./...","go test ./..."],
 "c":["make"],
 "cpp":["cmake -S . -B build","cmake --build build --config Release"],
 "java":["mvn -q test"],
 "csharp":["dotnet build --nologo","dotnet test --no-restore"],
}
def detect(root):
 p=Path(root)
 checks=[("python","pyproject.toml"),("python","requirements.txt"),("typescript","tsconfig.json"),("javascript","package.json"),("rust","Cargo.toml"),("go","go.mod"),("csharp", "*.csproj"),("java","pom.xml"),("cpp","CMakeLists.txt"),("c","Makefile")]
 for lang,marker in checks:
  if any(p.glob(marker)): return lang
 return "unknown"
def discover_tests(root,lang):
 p=Path(root); out=[]
 patterns={"python":["test_*.py","*_test.py"],"javascript":["*.test.js","*.spec.js"],"typescript":["*.test.ts","*.spec.ts"],"go":["*_test.go"],"rust":["tests"],"java":["src/test"],"csharp":["*Tests.cs"]}
 for pat in patterns.get(lang,[]):
  out.extend(str(x.relative_to(p)).replace("\\","/") for x in p.rglob(pat))
 return sorted(set(out))[:500]
def commands(root,lang):
 custom=os.getenv("DREAMCODER_BUILD_COMMAND","").strip()
 test=os.getenv("DREAMCODER_TEST_COMMAND","").strip()
 if custom:return [custom]+([test] if test else [])
 return BUILDERS.get(lang,[])[:]
def execute(root,cmd,network=False,timeout=300):
 if sandbox_available(): return sandbox_run(root,cmd,timeout,network)
 try:
  p=subprocess.run(cmd,cwd=root,shell=True,capture_output=True,text=True,timeout=timeout)
  return {"ok":p.returncode==0,"exit_code":p.returncode,"stdout":p.stdout,"stderr":p.stderr,"sandboxed":False}
 except subprocess.TimeoutExpired as e:return {"ok":False,"exit_code":-1,"stdout":e.stdout or "","stderr":e.stderr or "timeout","timeout":True,"sandboxed":False}
def diagnostics(result):
 text=(result.get("stderr") or "")+"\n"+(result.get("stdout") or "")
 return [{"file":m.group(1),"line":int(m.group(2)) if m.group(2) else None,"message":m.group(3).strip()} for m in re.finditer(r"(?m)([^:\n]+):(\d+)?(?::\d+)?:\s*(?:error|Error|ERROR)[: ]*([^\n]+)",text)][:100]
def snapshot(root):
 import shutil
 backup=Path(root).parent/(Path(root).name+".dreamcoder-repair-backup")
 if backup.exists(): shutil.rmtree(backup)
 shutil.copytree(root,backup,ignore=shutil.ignore_patterns(".git","node_modules",".venv","__pycache__","build","dist"))
 return str(backup)
def restore(root,backup):
 import shutil
 rp=Path(root); bp=Path(backup)
 for p in rp.iterdir():
  if p.name==".git":continue
  if p.is_dir():shutil.rmtree(p)
  else:p.unlink()
 for p in bp.iterdir():
  dest=rp/p.name
  if p.is_dir():shutil.copytree(p,dest)
  else:shutil.copy2(p,dest)
def run(root,network=False):
 lang=detect(root); tests=discover_tests(root,lang); backup=snapshot(root); history=[]; cmds=commands(root,lang)
 for cmd in cmds:
  res=execute(root,cmd,network)
  res["command"]=cmd; res["diagnostics"]=diagnostics(res); history.append(res)
  if not res["ok"]: return {"ok":False,"language":lang,"tests":tests,"backup":backup,"results":history,"repair_required":True}
 return {"ok":True,"language":lang,"tests":tests,"backup":backup,"results":history,"repair_required":False}
