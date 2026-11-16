#!/usr/bin/env python3
import json,glob
sets={}
for p in glob.glob("manifests/*.jsonl"):
 r=[json.loads(x) for x in open(p) if x.strip()];sets[p]={"queries":len({x["query_id"] for x in r}),"scenes":len({x["scene_id"] for x in r})}
print(json.dumps(sets,indent=2,sort_keys=True))
