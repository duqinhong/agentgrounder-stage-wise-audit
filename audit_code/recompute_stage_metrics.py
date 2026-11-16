#!/usr/bin/env python3
import csv,json,sys
rows=list(csv.DictReader(open(sys.argv[1] if len(sys.argv)>1 else "derived_results/per_query_stage_public.csv")))
def b(x):return str(x).lower()=="true"
out={"queries":len(rows),"scenes":len({r["scene_id"] for r in rows}),"thresholds":{}}
for tag,t in [("025",0.25),("05",0.5)]:
 c=sum(b(r[f"correct_{tag}"]) for r in rows);p=sum(b(r[f"pool_present_{tag}"]) for r in rows)
 wrong=[r for r in rows if b(r[f"pool_present_{tag}"]) and not b(r[f"correct_{tag}"])]
 out["thresholds"][tag]={"threshold":t,"selected_correct":c,"pool_present":p,"pool_present_final_wrong_exposure":{s:sum(r[f"exposure_{tag}"]==s for r in wrong) for s in ("exposed_yes","exposed_no","unknown")}}
print(json.dumps(out,indent=2,sort_keys=True))
