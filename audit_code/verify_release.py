#!/usr/bin/env python3
import hashlib,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1];bad=[]
for line in (root/"SHA256SUMS").read_text().splitlines():
 h,rel=line.split("  ",1);p=root/rel;actual=hashlib.sha256(p.read_bytes()).hexdigest()
 if h!=actual:bad.append([rel,h,actual])
print("PASS" if not bad else bad);sys.exit(bool(bad))
