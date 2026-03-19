## Why

The v5 orchestration run (sales-raketa, 5 changes, 75 min, 3.3M tokens) exposed several efficiency and reliability issues. Merge conflict resolution wasted tokens by trying sonnet first on large conflicts that always time out. The stale loop-state check spams 100+ identical log lines per run. Parallel changes that modify shared files (e.g., conventions docs) cause guaranteed merge conflicts. Replan cycle boundaries are invisible in the TUI and logs. The TUI token counter flashes to zero during replan. There is no self-restart mechanism if the orchestrator process crashes.

## What Changes

- **Merge model selection**: Skip sonnet for large conflicts (>200 lines), go directly to opus. Saves ~10K tokens + 300s per large conflict.
- **Stale warning debounce**: Downgrade the "loop-state stale but PID alive" message from `log_info` to `log_debug`, or rate-limit to once per 5 minutes per change. Eliminates 100+ noise lines per run.
- **Shared resource hint in planner prompt**: Add ~5 lines to decomposition prompt warning about parallel changes that modify the same shared files. Prevents guaranteed merge conflicts.
- **Cycle boundary markers**: Add explicit `===== REPLAN CYCLE N =====` log separator, `cycle_started_at` in state, and TUI visual boundary between cycles.
- **TUI token persistence**: Ensure `prev_total_tokens` is read immediately on replan so the token counter never displays zero.
- **Sentinel wrapper**: A minimal `set-sentinel` bash script (~20 lines) that restarts the orchestrator on crash, with backoff. No LLM — just a process supervisor.

## Capabilities

### New Capabilities
- `orchestrator-sentinel`: Self-restart wrapper for orchestrator crash recovery

### Modified Capabilities
- `merge-conflict-resolution`: Size-based model selection to skip sonnet on large conflicts
- `orchestration-engine`: Stale warning debounce, cycle boundary markers, shared resource planner hint
- `orchestrator-tui`: Token counter persistence across replan cycles

## Impact

- `bin/wt-merge`: Model selection logic in `llm_resolve_conflicts()` (~5 lines)
- `bin/set-orchestrate`: Stale log line (~1 line), planner prompt (~5 lines), cycle boundary (~10 lines)
- `gui/tui/orchestrator_tui.py`: Token display logic (~5 lines)
- `bin/set-sentinel`: New file (~20 lines)
