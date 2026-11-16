# AgentGrounder stage-wise audit

Reproducibility materials for **Beyond Candidate Recall: Explainable Stage-Wise Auditing of Multimodal Agents for 3D Visual Grounding**.

The repository implements the Pool–Exposure–Selection–Execution audit, publishes identifier-only frozen partition manifests, derived aggregate/per-query audit states, the hash-stratified 32-case provenance index, and release verification tools. No licensed 3D assets, images, model weights, embeddings, or raw logs are redistributed.

## Verified partitions

| Partition | Queries | Scenes | Source |
|---|---:|---:|---|
| Independent archive | 7,952 | 120 | ScanRefer validation |
| Exposure500 rerun | 500 | 98 | Independent archive subset |
| Canonical dev200 | 200 | 20 | ScanRefer training |
| Second development set | 200 | 148 | ScanRefer training |
| CompareGround3D calibration | 7,079 | 112 | ScanRefer training |

Canonical and second development sets share zero queries but five scenes. Exposure500's 120-scene value in an earlier table referred to its parent archive; the sample itself covers 98 scenes.

## Quick verification

```bash
python audit_code/verify_release.py
python audit_code/audit_partitions.py
python audit_code/recompute_stage_metrics.py
```

See `DATA_AVAILABILITY.md` and `docs/RUN_COMMANDS.md` for reconstruction from legally obtained third-party data.
