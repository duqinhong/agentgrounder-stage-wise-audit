# Pool–Exposure–Selection–Execution

* **Pool:** whether any frozen proposal reaches the IoU threshold.
* **Exposure:** whether a qualifying candidate ID is documented in a successful Tool response delivered to the model. Requests, explanations, OCR, and final predictions do not count as delivery. Incomplete evidence is `unknown`.
* **Selection:** whether the final valid candidate has IoU at or above the threshold.
* **Execution:** whether the run produced a protocol-valid candidate ID; invalid output and service/runtime failures remain in the denominator.

GT and IoU are joined only after GT-free trajectories are frozen. See `audit_code/recompute_stage_metrics.py`.
