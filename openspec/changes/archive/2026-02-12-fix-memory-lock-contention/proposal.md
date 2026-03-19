## Why

`set-memory remember` silently drops data when another process (notably the GUI's FeatureWorker, which polls every 15s) holds the RocksDB database open. RocksDB only allows one process to open a storage directory at a time. The `run_shodh_python` helper swallows all errors (`2>/dev/null | grep -v "^⭐" || true`), making these failures invisible. This leads to intermittent, silent data loss.

## What Changes

- Add `flock`-based serialization in `set-memory` so all RocksDB access is mutually exclusive at the shell level, preventing concurrent open attempts.
- Replace the `grep -v "^⭐"` banner filtering with Python-level suppression (`sys._shodh_star_shown = True`), eliminating the grep pipe that masks exit codes.
- Make Python errors visible by removing the blanket `2>/dev/null` — redirect stderr to a log file instead, so failures can be diagnosed.
- Ensure `cmd_remember` returns a meaningful exit code on failure instead of always exiting 0.

## Capabilities

### New Capabilities

- `memory-concurrency`: Serialization and error handling for concurrent set-memory access across processes.

### Modified Capabilities

_None — no existing spec-level requirements change. This is a reliability fix to the internal implementation._

## Impact

- **Code**: `bin/set-memory` — the `run_shodh_python` function, `cmd_remember`, and `cmd_status` functions.
- **Dependencies**: Requires `flock` (part of `util-linux`, available on all supported Linux/macOS systems).
- **Systems**: GUI FeatureWorker, agent sessions, and any concurrent callers of `set-memory` will be serialized through a per-project lock file at `/tmp/set-memory-<project>.lock`.
