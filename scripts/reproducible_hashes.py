#!/usr/bin/env python3
from pathlib import Path
import hashlib,sys
root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(p for p in root.rglob("*") if p.is_file() and p.name!="SHA256SUMS.txt")
for p in files:
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    print(h,p.relative_to(root))
