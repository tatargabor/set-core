## Why

The shodh-memory audit (`docs/research-shodh-memory-audit.md`) revealed that we only use ~35% of shodh-memory's API surface. The most impactful gap is `proactive_context()` — an API that auto-surfaces relevant memories based on conversational context with relevance scores, eliminating the need for carefully crafted recall queries. Additionally, the `set-memory remember` CLI passes only 3 of 7 available parameters (missing metadata, entities, is_failure, is_anomaly), and several useful recall/cleanup methods have no CLI exposure.

## What Changes

- **New `set-memory proactive` command**: Calls `proactive_context()` Python API instead of `recall()`. Returns memories with `relevance_score` and `relevance_reason`. Designed as primary recall method for hooks.
- **New `set-memory stats` command**: Shows memory quality diagnostics — type distribution, tag distribution, importance histogram, noise ratio, graph health.
- **New `set-memory cleanup` command**: Runs `forget_by_importance(threshold)` to remove low-value memories. Default threshold 0.2.
- **Extended `set-memory remember`**: Add `--metadata JSON`, `--failure`, `--anomaly` flags to expose the full `remember()` API.
- **Extended `set-memory recall`**: Add `--tags-only` flag to use `recall_by_tags()` (50x faster for structured lookups), `--min-importance` filter.
- **Hook upgrade**: Replace `set-memory recall` in `wt-hook-memory-recall` with `set-memory proactive` for better context-aware retrieval on change boundaries.

## Capabilities

### New Capabilities
- `proactive-recall`: The `set-memory proactive` command and its integration into hooks for context-aware memory retrieval
- `memory-diagnostics`: The `set-memory stats` and `set-memory cleanup` commands for memory quality monitoring and maintenance

### Modified Capabilities
- `memory-cli`: Extended remember flags (--metadata, --failure, --anomaly) and recall flags (--tags-only, --min-importance)
- `smart-memory-recall`: Hook upgrade from recall to proactive_context

## Impact

- **`bin/set-memory`**: New commands (proactive, stats, cleanup) and extended flags on existing commands (remember, recall)
- **`bin/wt-hook-memory-recall`**: Replace `set-memory recall` with `set-memory proactive`
- **No breaking changes**: All existing commands retain current behavior. New flags are additive.
- **Dependencies**: shodh-memory >= 0.1.75 (already installed, proactive_context API confirmed working)
