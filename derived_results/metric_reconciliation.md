# Independent metric reconciliation

Frozen set: 7952 queries, 120 scenes. Original data were read only.

## IoU ≥ 0.25
Full-pool Candidate Recall: 7395/7952 = 92.9955%.
Valid baseline prediction: 7918/7952; selected correct: 3872/7952.
A/B/C/D (failure-separate classification): {'B': 3492, 'A': 3872, 'C': 554, 'D': 34}.
A+B = 7364; difference from full-pool recall = 31.

## IoU ≥ 0.5
Full-pool Candidate Recall: 6704/7952 = 84.3058%.
Valid baseline prediction: 7918/7952; selected correct: 3477/7952.
A/B/C/D (failure-separate classification): {'B': 3199, 'A': 3477, 'C': 1242, 'D': 34}.
A+B = 6676; difference from full-pool recall = 28.

At @0.25 and @0.5, candidate-present failed/invalid queries are enumerated in `reconciliation_gap_queries.csv`. The prior A/B/C/D makes failure state D regardless of pool availability; full-pool recall still counts these queries. Threshold uses IoU ≥ t; all 7952 queries remain in the denominator.
Raw recomputation versus archived per-query candidate recall mismatches: 0 (see summary.json).
