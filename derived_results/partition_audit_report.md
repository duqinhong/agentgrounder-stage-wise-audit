# Partition audit

All counts were recomputed from unique `query_id` and `scene_id` values, not copied from prior reports.

* Canonical dev200: **200 queries / 20 scenes**, source: **ScanRefer training**.
* Second development set: **200 queries / 148 scenes**, source: **ScanRefer training**. Its overlap with canonical dev200 is **0 queries / 5 scenes**.
* Exposure500: **500 queries / 98 scenes**. All queries are in the 7,952-query independent archive: **0 outside**. All sample scenes are among the archive's 120 scenes.
* CompareGround3D calibration: **7,079 queries / 112 scenes**, source: **ScanRefer training**; overlap with the 120-scene independent archive: **0 scenes**.

## Corrections to manuscript Table 5

The table value `148 scenes` for the second development set is compared against the verified value **148** from `<RESTRICTED_LOCAL_ARTIFACT>`. The table value `120 scenes` for the rerun sample describes its parent archive; the 500 selected queries themselves cover **98** scenes according to `<RESTRICTED_LOCAL_ARTIFACT>`. Canonical dev200's source is **ScanRefer training**, verified against the official train and validation annotation scene sets.
