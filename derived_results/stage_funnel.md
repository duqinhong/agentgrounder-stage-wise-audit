# Pool → exposure → correct funnel

Exposure is established only from ID-bearing tool responses or ID-bearing rendered-image replies in the stored trace. Missing trace/image evidence is `unknown`; a final explanation is never used as exposure evidence.

## IoU ≥ 0.25
Pool present: 7395/7952
Exposure evidence among all pool-present: {'exposed_yes': 3899, 'unknown': 3474, 'exposed_no': 22}
Selected correct: 3872/7952; selected correct after documented exposure: 2192
Pool present, selected wrong: 3523
Exposure among these wrong cases: {'exposed_yes': 1707, 'unknown': 1794, 'exposed_no': 22}
Recoverable tool log: 4345/7952; queries with image message: 3965/7952.

## IoU ≥ 0.5
Pool present: 6704/7952
Exposure evidence among all pool-present: {'exposed_yes': 3547, 'unknown': 3140, 'exposed_no': 17}
Selected correct: 3477/7952; selected correct after documented exposure: 1995
Pool present, selected wrong: 3227
Exposure among these wrong cases: {'exposed_yes': 1552, 'unknown': 1658, 'exposed_no': 17}
Recoverable tool log: 4345/7952; queries with image message: 3965/7952.

`exposed_yes` proves an eligible ID appeared in a logged tool response. `exposed_no` means the recoverable text tool replies contained no eligible ID and no image message; it does not prove the model could never infer the object. Image-only messages with unavailable/ambiguous candidate IDs remain unknown.