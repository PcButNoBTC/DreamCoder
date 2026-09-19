from pathlib import Path
import hashlib,sys
def manifest(root):
    root=Path(root); out=[]
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        if p.name=="SHA256SUMS.txt": continue
        out.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}")
    return "\n".join(out)+"\n"
if __name__=="__main__":
    if len(sys.argv)<2: raise SystemExit("usage: verify_reproducible.py DIR [EXPECTED]")
    data=manifest(sys.argv[1])
    if len(sys.argv)>2 and data!=Path(sys.argv[2]).read_text(): raise SystemExit("artifact manifest mismatch")
    print(data,end="")
