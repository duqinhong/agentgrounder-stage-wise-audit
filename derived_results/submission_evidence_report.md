# Submission evidence check

Frozen independent set: **7952 queries / 120 scenes**. Read-only CPU analysis; no model inference.

| IoU | Accuracy | Candidate Recall | A/B/C/D | Pool present, Agent wrong: delivered / no delivery / unknown |
|---|---:|---:|---|---|
| 0.25 | 3872/7952 (48.69%) | 7395/7952 (93.00%) | 3872/3492/554/34 | 1707/22/1794 |
| 0.5 | 3477/7952 (43.72%) | 6704/7952 (84.31%) | 3477/3199/1242/34 | 1552/17/1658 |

The @0.25 A+B count is 7364; 31 failed queries had a qualifying proposal and were classified D, while full-pool recall counts them. At @0.5 the corresponding gap is 28.

The `exposed_wrong_outcome_split.csv` lists every query ID, state-file path and SHA, trace path and SHA, and the tool-message section containing a qualifying candidate ID. Exposure denotes ID delivery in the recorded tool reply; it is not a human judgement of visual recognition.

| IoU | Valid prediction, wrong | invalid_output | model_service_error |
|---|---:|---:|---:|
| 0.25 | 1692 | 15 | 0 |
| 0.5 | 1539 | 13 | 0 |

Manual review: 32 fixed-hash cases (8 per category); blank human labels in `manual_review_template.csv`. Unknown cases were sampled only where a tool trace is recoverable, so reviewers can inspect the incomplete evidence. The category label is an audit stratum, not an annotation.

Numerical inconsistencies: **0**. All listed archived totals and both threshold funnels agree with the frozen per-query audit.
