## Why

The Ralph loop's `detect_next_change_action()` in `wt-loop` scans ALL OpenSpec changes alphabetically and picks the first incomplete one. When the orchestrator dispatches a specific change to a worktree, the agent ignores the assigned task and works on whichever unfinished change comes first alphabetically (e.g., `email-sandbox` instead of `orchestration-smoke-config`). This makes orchestrated multi-change workflows unreliable.

## What Changes

- Add `--change <name>` flag to `wt-loop start` that gets stored in `loop-state.json`
- Modify `detect_next_change_action()` to accept an optional change name parameter — when provided, only inspect that single change; when absent, **skip detection entirely** (let the user's task prompt and OpenSpec skills handle selection)
- Modify `build_prompt()` to pass the stored change name to the detect function
- Modify `set-orchestrate` `dispatch_change()` to pass `--change "$change_name"` when starting the Ralph loop

## Capabilities

### New Capabilities

- `scoped-change-detection`: wt-loop respects an explicit `--change` flag to scope OpenSpec detection to a single change, preventing cross-contamination between orchestrated worktrees

### Modified Capabilities

## Impact

- `bin/wt-loop`: `detect_next_change_action()`, `build_prompt()`, `cmd_start()`, `init_loop_state()`
- `bin/set-orchestrate`: `dispatch_change()` (one-line addition of `--change` flag)
- Solo Ralph loop behavior changes: without `--change`, detection no longer runs — the agent relies on its task prompt and OpenSpec skill auto-selection instead of hardcoded alphabetical scanning
