# Excluded files

The release intentionally excludes: ScanNet point clouds/PLY/NPZ/RGB; rendered images; original ScanRefer annotation JSON; Mask3D proposals where redistribution is unclear; model weights; embedding caches; raw AI messages and tool logs; local query-state files; checkpoints; credentials; API tokens; SSH configuration; internal hostnames and addresses. For the 32 cases, only identifiers, cryptographic hashes, evidence type, and a restricted-evidence locator are retained. Missing predictions and `unknown` states were not reconstructed.
