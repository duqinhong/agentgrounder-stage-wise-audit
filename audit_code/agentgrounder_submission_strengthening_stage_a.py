#!/usr/bin/env python3
"""Read-only offline strengthening audit for the frozen AgentGrounder paper evidence."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(os.environ.get('AGENTGROUNDER_DATA_ROOT', 'licensed_data_root'))
OUT = Path(os.environ.get('AUDIT_OUTPUT', 'outputs/offline_stage_a'))
AUDIT = Path(os.environ.get('INDEPENDENT_AUDIT', 'inputs/independent_audit'))
PER = AUDIT / 'per_query_stage.csv'
SRC_MANIFEST = AUDIT / 'source_manifest.json'
BASE = Path(os.environ.get('BASELINE_ARCHIVE', 'licensed_data_root/baseline'))
DATA = Path(os.environ.get('PROPOSAL_ARCHIVE', 'licensed_data_root/proposals'))
TRACE = Path(os.environ.get('TRACESELECT_ARCHIVE', 'inputs/traceselect'))
ANCHOR = Path(os.environ.get('ANCHORGUARD_ARCHIVE', 'inputs/anchorguard'))
TRACE_PROTOCOL = Path(os.environ.get('TRACE_PROTOCOL', 'configs/traceselect3d_dev200_protocol.json'))
TRACE_CONFIG = Path(os.environ.get('TRACE_CONFIG', 'configs/traceselect3d_stage1_config.json'))
ANN = Path(os.environ.get('SCANREFER_VAL_JSON', 'licensed_data_root/ScanRefer_filtered_val.json'))
BOOT_REPS = 10_000
BOOT_SEED = 20261104


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write_json(name: str, obj) -> None:
    p = OUT / name
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + '\n')


def quantile(xs, q):
    ys = sorted(xs)
    if not ys:
        return None
    z = (len(ys) - 1) * q
    lo, hi = math.floor(z), math.ceil(z)
    if lo == hi:
        return ys[lo]
    return ys[lo] * (hi - z) + ys[hi] * (z - lo)


def wilson(k: int, n: int, z: float = 1.959963984540054):
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - half, center + half]


def logchoose(n, k):
    if k < 0 or k > n:
        return float('-inf')
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact_two_sided(a, b, c, d):
    r1, r2, c1 = a + b, c + d, a + c
    n = r1 + r2
    lo, hi = max(0, c1 - r2), min(r1, c1)
    def prob(x):
        return math.exp(logchoose(r1, x) + logchoose(r2, c1 - x) - logchoose(n, c1))
    p0 = prob(a)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= p0 + 1e-15))


def exact_binomial_two_sided(k, n, p=0.5):
    if n == 0:
        return 1.0
    probs = [math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(n+1)]
    p0 = probs[k]
    return min(1.0, sum(x for x in probs if x <= p0 + 1e-15))


def boolv(v):
    return str(v).lower() == 'true'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def source_manifest(paths):
    rows = []
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f'authoritative input missing: {p}')
        rows.append({'path': str(p), 'sha256': sha256(p), 'bytes': p.stat().st_size})
    write_json('source_manifest.json', {'inputs': rows, 'analysis_script': str(Path(__file__).resolve()),
                                        'analysis_script_sha256': sha256(Path(__file__).resolve())})
    return {x['path']: x['sha256'] for x in rows}


def exposure_analysis(rows, source_hashes):
    # Reuse the authoritative frozen source index instead of reopening thousands
    # of archived trace files on slow storage.
    indexed_hashes = {x['path']: x['sha256'] for x in read_csv(AUDIT/'source_files.csv')}
    detail = []
    summary = {}
    for t, tag in [(0.25, '025'), (0.5, '05')]:
        groups = {'final_correct': Counter(), 'pool_present_final_wrong': Counter()}
        evidence = defaultdict(int)
        for r in rows:
            correct = boolv(r[f'correct_{tag}'])
            pool = boolv(r[f'pool_present_{tag}'])
            if correct:
                group, state = 'final_correct', r[f'exposure_all_{tag}']
            elif pool:
                group, state = 'pool_present_final_wrong', r[f'exposure_{tag}']
            else:
                continue
            groups[group][state] += 1
            if state == 'exposed_yes':
                src = 'qualifying candidate ID in parsed Tool response'
            elif state == 'exposed_no':
                src = 'complete recoverable text trace; no qualifying ID and no image message'
            else:
                src = 'incomplete or image-ambiguous evidence'
            trace_hash = indexed_hashes.get(r.get('trace_path',''), '')
            detail.append({
                'query_id': r['query_id'], 'scene_id': r['scene_id'], 'threshold': t,
                'final_correct': correct, 'pool_present': pool, 'exposure_state': state,
                'evidence_source': src, 'trace_recoverable': r['trace_recoverable'],
                'tool_events': r[f'tool_events_{tag}'], 'image_messages': r[f'image_messages_{tag}'],
                'source_artifact_path': r['trace_path'] or str(PER),
                'source_artifact_sha256': trace_hash or source_hashes[str(PER)],
            })
            evidence['trace_recoverable'] += boolv(r['trace_recoverable'])
            evidence['image_message'] += int(r[f'image_messages_{tag}'] or 0) > 0
        stats = {}
        for g, c in groups.items():
            n = sum(c.values()); det = c['exposed_yes'] + c['exposed_no']
            stats[g] = {
                'denominator': n, 'counts': dict(c),
                'proportions': {s: c[s]/n if n else None for s in ['exposed_yes','exposed_no','unknown']},
                'wilson95': {s: wilson(c[s], n) for s in ['exposed_yes','exposed_no','unknown']},
                'determinable_denominator': det,
                'exposed_yes_among_determinable': c['exposed_yes']/det if det else None,
                'exposed_yes_among_determinable_wilson95': wilson(c['exposed_yes'], det),
            }
        a = groups['final_correct']['exposed_yes']; b = groups['final_correct']['exposed_no']
        c = groups['pool_present_final_wrong']['exposed_yes']; d = groups['pool_present_final_wrong']['exposed_no']
        stats['determinable_comparison'] = {
            'table': {'correct_yes': a, 'correct_no': b, 'wrong_yes': c, 'wrong_no': d},
            'fisher_exact_two_sided_p': fisher_exact_two_sided(a,b,c,d),
            'odds_ratio': (a*d)/(b*c) if b*c else None,
        }
        stats['evidence_coverage'] = {
            'included_rows': len([x for x in detail if x['threshold'] == t]),
            'trace_recoverable': evidence['trace_recoverable'],
            'image_message_rows': evidence['image_message'],
        }
        summary[tag] = stats
    fields = list(detail[0])
    with (OUT/'exposure_correct_vs_wrong_per_query.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(detail)
    write_json('exposure_correct_vs_wrong_summary.json', summary)
    md = ['# Correct versus wrong exposure baseline','',
          'Exposure follows the frozen Tool-response-only rule. Requests, explanations, and OCR are excluded; GT is joined only after trace freezing.','']
    for tag, s in summary.items():
        md += [f"## IoU {0.25 if tag=='025' else 0.5}",
               f"- Correct: {s['final_correct']['counts']} (N={s['final_correct']['denominator']}).",
               f"- Pool-present final-wrong: {s['pool_present_final_wrong']['counts']} (N={s['pool_present_final_wrong']['denominator']}).",
               f"- Determinable exposed-yes rates: correct {s['final_correct']['exposed_yes_among_determinable']:.4%}; wrong {s['pool_present_final_wrong']['exposed_yes_among_determinable']:.4%}.",
               f"- Fisher exact two-sided p={s['determinable_comparison']['fisher_exact_two_sided_p']:.6g}.",'']
    (OUT/'exposure_correct_vs_wrong.md').write_text('\n'.join(md)+'\n')
    return summary


def transitions_from_iou(path, kind):
    rows = read_csv(path)
    out=[]
    for r in rows:
        ai=float(r['A_iou']); bi=float(r['B_iou'])
        out.append({'query_id':r['query_id'],'scene_id':r['scene_id'],'A_iou':ai,'B_iou':bi,'source':kind})
    return out


def bootstrap_paired(rows, threshold, cluster=False):
    rng=random.Random(BOOT_SEED + int(threshold*1000) + (100000 if cluster else 0))
    by_scene=defaultdict(list)
    for r in rows: by_scene[r['scene_id']].append(r)
    scenes=sorted(by_scene)
    vals=[]; utils=[]
    for _ in range(BOOT_REPS):
        if cluster:
            sample=[]
            for s in (rng.choice(scenes) for _ in scenes): sample.extend(by_scene[s])
        else:
            sample=[rng.choice(rows) for _ in rows]
        ac=[x['A_iou']>=threshold for x in sample]; bc=[x['B_iou']>=threshold for x in sample]
        wr=sum((not a) and b for a,b in zip(ac,bc)); rw=sum(a and (not b) for a,b in zip(ac,bc))
        vals.append((sum(bc)-sum(ac))/len(sample)); utils.append((wr-2*rw)/len(sample))
    return {'replicates':BOOT_REPS,'seed':BOOT_SEED,'method':'scene_cluster' if cluster else 'query',
            'accuracy_difference_ci95':[quantile(vals,.025),quantile(vals,.975)],
            'utility_rate_ci95':[quantile(utils,.025),quantile(utils,.975)]}


def merged_exposure_experiments(source_hashes):
    trace_rows=transitions_from_iou(TRACE/'per_query_posthoc.csv','canonical_dev200')
    anchor_rows=transitions_from_iou(ANCHOR/'labeled_switch_examples.csv','anchorguard_stage1')
    overlap=sorted({x['query_id'] for x in trace_rows}&{x['query_id'] for x in anchor_rows})
    tp=json.loads(TRACE_PROTOCOL.read_text()); td=json.loads((TRACE/'decision_freeze.json').read_text())
    ad=json.loads((ANCHOR/'decision_freeze.json').read_text()); ap=json.loads((ANCHOR/'prediction_freeze.json').read_text())
    checks={
      'query_intersection_zero':len(overlap)==0,
      'row_counts':[len(trace_rows),len(anchor_rows)],
      'same_exposure_config':td['exposure_config_sha256']==ad['exposure_config_sha256']==ap['exposure_config_sha256']==tp['exposure_config_sha256'],
      'same_agent_config':tp['original_agent_config_sha256']==ap['agent_config_sha256'],
      'same_prompt':tp['system_prompt_sha256']==ap['prompt_sha256'],
      'same_model_digest':tp['agent_model_digest']==ap['model_digest'],
      'A_definition':tp['arms']['A'], 'B_definition':tp['arms']['B'],
      'both_frozen':json.loads((TRACE/'prediction_freeze.json').read_text())['status']=='predictions_frozen' and ap['status']=='gtfree_predictions_frozen',
      'overlap_query_ids':overlap,
    }
    can_merge=all(checks[k] for k in ['query_intersection_zero','same_exposure_config','same_agent_config','same_prompt','same_model_digest','both_frozen'])
    write_json('exposure_experiment_merge_audit.json',{'can_merge':can_merge,'checks':checks})
    if not can_merge: return None
    rows=trace_rows+anchor_rows; report={'N':len(rows),'experiments':Counter(x['source'] for x in rows)}
    for t,tag in [(0.25,'025'),(0.5,'05')]:
        ac=[x['A_iou']>=t for x in rows]; bc=[x['B_iou']>=t for x in rows]
        wr=sum((not a) and b for a,b in zip(ac,bc));rw=sum(a and (not b) for a,b in zip(ac,bc))
        cc=sum(a and b for a,b in zip(ac,bc));ww=sum((not a) and (not b) for a,b in zip(ac,bc))
        report[tag]={'threshold':t,'N':len(rows),'A_correct':sum(ac),'B_correct':sum(bc),'WR':wr,'RW':rw,'CC':cc,'WW':ww,
                     'accuracy_difference':(sum(bc)-sum(ac))/len(rows),'utility':wr-2*rw,
                     'mcnemar_exact_two_sided_p':exact_binomial_two_sided(min(wr,rw),wr+rw),
                     'WR_vs_RW_exact_binomial_two_sided_p':exact_binomial_two_sided(wr,wr+rw),
                     'query_bootstrap':bootstrap_paired(rows,t,False),'scene_cluster_bootstrap':bootstrap_paired(rows,t,True)}
    write_json('merged_exposure_only_statistics.json',report)
    return report


def subgroup_analysis(rows):
    annotations=json.loads(ANN.read_text())
    ann={(x['scene_id'],str(x['object_id']),str(x['ann_id'])):x for x in annotations}
    proposal_cache={}
    group_rows=[]
    missing=[]
    for r in rows:
        qid=r['query_id']; m=re.match(r'^(scene\d{4}_\d{2})__target-(\d+)__ann-(\d+)__',qid)
        if not m: missing.append({'query_id':qid,'reason':'query_id_parse'});continue
        key=(m.group(1),m.group(2),m.group(3)); a=ann.get(key)
        if not a: missing.append({'query_id':qid,'reason':'official_annotation_missing'});continue
        sc=m.group(1)
        if sc not in proposal_cache:
            pp=DATA/'proposals'/f'{sc}.json'; proposal_cache[sc]=json.loads(pp.read_text())
        target_label=a['object_name'].strip().lower()
        # Frozen proposal JSON uses the semantic class field `target`.
        same=sum(str(x.get('target','')).strip().lower()==target_label for x in proposal_cache[sc])
        if same < 1:
            missing.append({'query_id':qid,'reason':'zero_exact_same_class_proposals'})
            continue
        bucket='1' if same==1 else '2-4' if same<=4 else '5-9' if same<=9 else '>=10'
        group_rows.append((bucket,r))
    result={'unique_multiple':{'status':'unavailable','reason':'official ScanRefer annotation has no eval_type field and no authoritative one-to-one lookup was located'},
            'same_class_definition':'exact lowercase official object_name == proposal target','missing_alignment':missing,'buckets':{}}
    for b in ['1','2-4','5-9','>=10']:
        rr=[r for bb,r in group_rows if bb==b]; d={'N':len(rr)}
        for t,tag in [(0.25,'025'),(0.5,'05')]:
            n=len(rr); pool=sum(boolv(x[f'pool_present_{tag}']) for x in rr); cor=sum(boolv(x[f'correct_{tag}']) for x in rr)
            ex=Counter(x[f'exposure_all_{tag}'] for x in rr if boolv(x[f'pool_present_{tag}']))
            d[tag]={'candidate_recall':pool/n if n else None,'accuracy':cor/n if n else None,'pool_present':pool,'correct':cor,'exposure_pool_present':dict(ex)}
        result['buckets'][b]=d
    write_json('subgroup_analysis.json',result)
    with (OUT/'subgroup_analysis.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['bucket','N','candidate_recall_025','accuracy_025','exposed_yes_025','exposed_no_025','unknown_025','candidate_recall_05','accuracy_05','exposed_yes_05','exposed_no_05','unknown_05']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for b,d in result['buckets'].items():
            row={'bucket':b,'N':d['N']}
            for tag in ['025','05']:
                row[f'candidate_recall_{tag}']=d[tag]['candidate_recall'];row[f'accuracy_{tag}']=d[tag]['accuracy']
                for s in ['exposed_yes','exposed_no','unknown']:row[f'{s}_{tag}']=d[tag]['exposure_pool_present'].get(s,0)
            w.writerow(row)
    return result


def qualitative_case(rows):
    candidates=[]
    for r in rows:
        if boolv(r['pool_present_025']) and not boolv(r['correct_025']) and r['exposure_025']=='exposed_yes' and int(r['image_messages_025'] or 0)>0:
            trace=Path(r['trace_path'])
            if trace.exists():
                text=trace.read_text(errors='replace'); links=re.findall(r'!\[[^]]*\]\(([^)]+)\)',text)
                imgs=[(trace.parent/x).resolve() for x in links]
                imgs=[x for x in imgs if x.exists()]
                if imgs:candidates.append((hashlib.sha256(r['query_id'].encode()).hexdigest(),r,trace,imgs))
    if not candidates: raise RuntimeError('no fully auditable qualitative case')
    _,r,trace,imgs=sorted(candidates)[0]
    sc=r['scene_id']; qid=r['query_id']; m=re.match(r'^(scene\d{4}_\d{2})__target-(\d+)__ann-(\d+)__',qid)
    qstate=BASE/'query_state'/sc/f'{qid}.json'; prop=DATA/'proposals'/f'{sc}.json'; gt=DATA/'gt'/f'{sc}.json'; qlist=DATA/'query'/f'{sc}.json'
    state=json.loads(qstate.read_text()); q=state['query']
    manifest={'selection':'minimum SHA256(query_id) among frozen @0.25 pool-present, exposed_yes, final-wrong cases with an existing delivered image',
      'query_id':qid,'scene_id':sc,'query_text':q['caption'],'predicted_candidate_id':r['predicted_id'],
      'qualifying_proposal_ids':[int(x) for x in r['qualified_candidate_ids_025'].split(';') if x],
      'gt_object_id':int(q['target_id']),'threshold':0.25,
      'artifacts':[],'panel_layout':[
        '(a) GT-free query and proposal-pool overview',
        '(b) chronological Tool response excerpt with qualifying proposal ID highlighted',
        '(c) exact image delivered to the model, with no post-hoc GT overlay',
        '(d) final predicted proposal and explanation',
        '(e) post-hoc-only panel: GT bbox, qualifying proposal bbox, predicted bbox, and IoU'],
      'gt_display_restriction':'GT object/bbox may appear only in panel (e).'}
    for p,kind in [(qstate,'query_state'),(trace,'tool_trace'),(prop,'proposal_pool'),(gt,'gt_boxes'),(qlist,'query_list')]+[(x,'delivered_image') for x in imgs]:
        manifest['artifacts'].append({'kind':kind,'path':str(p),'sha256':sha256(p),'bytes':p.stat().st_size})
    write_json('qualitative_case_manifest.json',manifest)
    return manifest


def stratified_hash_select(items,n,salt):
    by=defaultdict(list)
    for r in items:by[r['scene_id']].append(r)
    for s in by:by[s].sort(key=lambda r:hashlib.sha256(f'{salt}|{r["query_id"]}'.encode()).hexdigest())
    scenes=sorted(by,key=lambda s:hashlib.sha256(f'{salt}|scene|{s}'.encode()).hexdigest())
    out=[];i=0
    while len(out)<n:
        progressed=False
        for s in scenes:
            if i<len(by[s]) and len(out)<n:out.append(by[s][i]);progressed=True
        if not progressed:break
        i+=1
    if len(out)!=n:raise RuntimeError(f'cannot select {n}: got {len(out)}')
    return out


def make_exposure500(rows):
    correct=[r for r in rows if boolv(r['correct_025'])]
    unknown=[r for r in rows if boolv(r['pool_present_025']) and not boolv(r['correct_025']) and r['exposure_025']=='unknown']
    a=stratified_hash_select(correct,250,'20261104|agentgrounder-exposure500')
    b=stratified_hash_select(unknown,250,'20261104|agentgrounder-exposure500')
    selected=[]
    for group,rr in [('historical_correct_025',a),('historical_pool_present_wrong_unknown_025',b)]:
        for r in rr:
            selected.append({'query_id':r['query_id'],'scene_id':r['scene_id'],'query_index':int(r['query_index']),
                             'historical_run_status':r['status'],'sampling_stratum':group,
                             'rank_key':hashlib.sha256(f'20261104|agentgrounder-exposure500|{r["query_id"]}'.encode()).hexdigest()})
    p=OUT/'exposure500_manifest.jsonl'
    with p.open('w',encoding='utf-8') as f:
        for r in selected:f.write(json.dumps(r,sort_keys=True)+'\n')
    (OUT/'exposure500_manifest.sha256').write_text(sha256(p)+'  exposure500_manifest.jsonl\n')
    audit={'rows':len(selected),'unique_query_ids':len({x['query_id'] for x in selected}),'scenes':len({x['scene_id'] for x in selected}),
           'strata':dict(Counter(x['sampling_stratum'] for x in selected)),'source_split':'frozen independent 7952 only',
           'development_overlap':0,'selection_uses_gt_fields':False,
           'model_input_exclusion':['sampling_stratum','historical_run_status','rank_key'],
           'selection_note':'Primary paper threshold @0.25 defines the two strata; no IoU, GT ID, correctness, or exposure label may be passed to the future model.'}
    write_json('split_and_leakage_audit.json',audit)
    # Historical observed independent runtime is used only for planning, not as a new benchmark.
    per_query=881305.1981819347/7952
    write_json('expected_runtime_estimate.json',{'basis':'frozen independent report elapsed_sec / 7952','seconds_per_query':per_query,
      'queries':500,'single_attempt_seconds':500*per_query,'single_attempt_hours':500*per_query/3600,
      'warning':'planning estimate only; retries and full logging overhead are not recorded and are excluded'})
    protocol='''# Complete logging protocol for the future 500-query rerun\n\nThis file is a manifest-only protocol. No rerun was started.\n\nFor every attempt, append atomically to an attempt ledger and save: all model input/output messages; ordered tool requests and tool responses; every delivered image file, path, and SHA-256; model/tool/image call counts; candidate order and its hash; final prediction; the original exception including service payload; and the result of ContextVar/per-run-state cleanup. The orchestration fields `sampling_stratum`, `historical_run_status`, and `rank_key` must never enter model messages, tools, or candidate generation. GT, IoU, correctness, qualifying IDs, and historical exposure labels remain unavailable until all 500 predictions and traces are frozen and hashed. Request-only events do not establish delivery. Each image-bearing response must record the exact image hash actually inserted into the model message. Attempts are append-only; failures cannot be replaced or backfilled from historical predictions.\n'''
    (OUT/'complete_logging_protocol.md').write_text(protocol)
    return audit


def official_comparison():
    obj={'official_sources':[
      {'title':'AgentGrounder official paper','url':'https://openreview.net/attachment?id=Ft2t57khSZ&name=pdf','accessed':'2026-11-05'},
      {'title':'AgentGrounder official code','url':'https://github.com/be2rlab/AgentGrounder','accessed':'2026-11-05'}],
      'comparison':{
       'official_scanrefer':{'sample':'1000-query stratified subsample preserving Unique/Multiple','acc_025':0.472,'acc_05':0.419,
          'proposal_source':'Mask3D','model':'Qwen3-VL-32B-Instruct','deployment':'Ollama via LangChain','gpus':'2 x NVIDIA RTX 4090',
          'quantization':'not recorded','context_length':'not recorded','invalid_or_service_failures_in_denominator':'not recorded'},
       'local_independent':{'sample':'7952 queries, 120 scenes','acc_025':0.4869215291750503,'acc_05':0.43724849094567403,
          'proposal_source':'Mask3D ScanNet200 archive','model':'qwen3-vl:32b-instruct','deployment':'Ollama via LangChain',
          'gpus':'8 x NVIDIA RTX 4090 across original/resume infrastructure','quantization':'Q4_K_M','context_length':16384,
          'invalid_or_service_failures_in_denominator':'yes; 34/7952 retained'},
       'comparability':'not the same evaluation sample; the official number is a 1000-query stratified subsample, whereas local results use a disjointly defined 7952-query subset of the official validation set. Differences must not be attributed causally to any configuration field.'}}
    write_json('official_agentgrounder_comparison.json',obj)
    return obj


def revision_plan(exposure_summary, merged, subgroup):
    p=[]
    p.append('# Manuscript revision plan\n')
    p.append('## Global framing\nReplace “four bottlenecks” with **four separately auditable stages**. The frozen evidence most directly establishes a large pool-to-answer gap and a conservative subset of selection/execution failures; incomplete traces prevent claiming that exposure is exhaustively measured.\n')
    p.append('## Direct replacement text\n')
    p.append('### Abstract (shortened)\n> We present a stage-wise evidence audit of a frozen agentic 3D grounding pipeline. On 7,952 ScanRefer queries from 120 scenes, final Acc@0.25/0.5 is 48.69%/43.72%, while full-pool Candidate Recall is 93.00%/84.31%. Recoverable tool traces establish a conservative lower bound of 1,707 IoU-0.25 errors in which a qualifying candidate ID was delivered before an incorrect or invalid final answer. Controlled exposure changes both wrong-to-right and right-to-wrong decisions, while two learned safeguards fail to improve scene-disjoint calibration. These results motivate reporting proposal availability, evidence delivery, candidate selection, and execution as separately auditable stages rather than treating Candidate Recall as an end-to-end diagnostic.\n')
    p.append('### Framework wording\n> Pool, Exposure, Selection, and Execution are four separately auditable stages. The framework does not assume that every stage is a bottleneck in every system. In this evaluation, the strongest direct evidence concerns the gap after pool availability, including documented cases in which qualifying candidate IDs were delivered but not selected correctly, plus execution failures retained in the denominator.\n')
    p.append('### Utility definition\n> We define the regression-sensitive utility as $U=WR-2RW$, where a right-to-wrong regression is assigned twice the cost of a wrong-to-right correction. The intervention passes this criterion only when $U>0$; $U=0$ is not a pass.\n')
    p.append('### Evidence package\n> The 32-case hash-stratified package is an AI-assisted supplementary provenance package for inspecting source traces and images. It is not a human-annotated error taxonomy and is removed from the main contribution list.\n')
    p.append('### CompareGround3D note\n> CompareGround3D was selected on a calibration set of $N=7,079$ queries. Reported percentage-point differences are computed from unrounded underlying proportions and may differ slightly from subtraction of displayed rounded percentages.\n')
    p.append('## Required edits\n- Move the 31-query Candidate Recall/A+B reconciliation from the abstract to Experimental Protocol or Results.\n- Remove unsupported claims that the findings generalize to multimodal or material-data analysis beyond the measured AgentGrounder/ScanRefer setting.\n- Present dev200 and the merged 400-query Exposure-only analysis as development interventions, not independent generalization evidence.\n- Keep Unknown as a first-class exposure state and state trace/image recovery coverage.\n- Report official AgentGrounder numbers only with the 1,000-query subsample caveat.\n')
    (OUT/'manuscript_revision_plan.md').write_text('\n'.join(p)+'\n')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    paths=[PER,SRC_MANIFEST,AUDIT/'summary.json',AUDIT/'source_files.csv',AUDIT/'output_hashes.json',
      TRACE/'per_query_posthoc.csv',TRACE/'decision_freeze.json',TRACE/'prediction_freeze.json',TRACE/'evaluation.json',
      TRACE_PROTOCOL,TRACE_CONFIG,ANCHOR/'labeled_switch_examples.csv',ANCHOR/'sample_freeze.json',ANCHOR/'decision_freeze.json',
      ANCHOR/'prediction_freeze.json',ANCHOR/'stage1_gate.json',ANN]
    hashes=source_manifest(paths)
    rows=read_csv(PER)
    assert len(rows)==7952 and len({x['query_id'] for x in rows})==7952
    exposure=exposure_analysis(rows,hashes)
    merged=merged_exposure_experiments(hashes)
    subgroup=subgroup_analysis(rows)
    qualitative_case(rows)
    make_exposure500(rows)
    official_comparison()
    revision_plan(exposure,merged,subgroup)
    # Final hashes exclude this file until all outputs exist.
    outputs={p.name:sha256(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='output_hashes.json'}
    write_json('output_hashes.json',outputs)
    write_json('run_status.json',{'status':'completed_offline_only','model_runs':0,'gpu_used':False,
      'frozen_inputs_modified':False,'exposure500_rerun_started':False,'other_splits_evaluated':False})
    # Refresh hash list to include run_status.
    outputs={p.name:sha256(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='output_hashes.json'}
    write_json('output_hashes.json',outputs)
    print(json.dumps({'status':'PASS offline Stage A','output':str(OUT),'files':len(list(OUT.iterdir())),'merged':merged is not None},indent=2))


if __name__=='__main__':
    main()
