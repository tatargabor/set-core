## Why

Core set-core scripts have grown into monoliths (1000-3700 lines each), making them hard to maintain, test, and develop incrementally. The 7 largest files contain mixed concerns — e.g., set-memory has CRUD, rules, todos, sync, migration, and UI all in one 3713-line bash script. This slows down both human and agent development because every change requires understanding the entire file.

## What Changes

- Extract logical modules from 7 monolithic scripts into `lib/` subdirectories
- Main scripts become thin dispatchers that `source` extracted lib files
- Add unit tests for each extracted module
- No CLI interface changes — purely internal restructuring
- No behavior changes — backward compatible

Phases (in priority order):
1. Extract editor subsystem (420 lines, 19 fn) from `wt-common.sh` to `lib/editor.sh`
2. Split `set-memory` (3713 lines) into 7 modules under `lib/memory/`
3. Split `wt-hook-memory` (1817 lines) into 5 modules under `lib/hooks/`
4. Refactor orchestration `state.sh` + `dispatcher.sh` into focused modules
5. Split `wt-loop` (2248 lines) into 4 modules under `lib/loop/`
6. Refactor `set-project` deploy_set_tools() into focused functions

## Capabilities

### New Capabilities
- `modular-source-structure`: Extraction of monolithic scripts into sourced lib/ modules with unit tests

### Modified Capabilities

## Impact

- `bin/wt-common.sh` — editor functions extracted to lib/
- `bin/set-memory` — split into 7 lib/memory/ modules
- `bin/wt-hook-memory` — split into 5 lib/hooks/ modules
- `bin/wt-loop` — split into 4 lib/loop/ modules
- `lib/orchestration/state.sh` — split into config/state/memory/utils
- `lib/orchestration/dispatcher.sh` — extract builder.sh and monitor.sh
- `bin/set-project` — deploy_set_tools() split into focused functions
- New `tests/unit/` directory with module-level tests
