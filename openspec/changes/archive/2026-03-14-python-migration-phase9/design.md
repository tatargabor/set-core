## Context

After Phase 8, the orchestration engine is 100% Python. Two major bash subsystems remain: the Ralph loop engine (`lib/loop/*`, 2,398 LOC — manages worktree agent iterations) and the Claude Code hook pipeline (`lib/hooks/*`, 1,822 LOC — runs on every tool use for memory, context injection, metrics). Both are complex state machines with heavy JSON processing.

## Goals / Non-Goals

**Goals:**
- Migrate `lib/loop/` (4 files, 2,398 LOC) to Python in `lib/set_orch/`
- Migrate `lib/hooks/` (5 files, 1,822 LOC) to new Python package `lib/set_hooks/`
- Update `bin/wt-loop` and `bin/set-memory-hooks` to call Python
- Maintain 1:1 behavioral parity
- Unit tests for all new modules

**Non-Goals:**
- Migrating `bin/*` CLI entry points (stay bash)
- Migrating `lib/memory/*` (legacy, being replaced by shodh-memory)
- Performance optimization beyond parity
- Changing hook event protocol or output format

## Decisions

1. **Loop engine (`lib/loop/` → `lib/set_orch/loop*.py`)**: Four tightly coupled modules become four Python modules. `engine.sh` → `loop.py` (main iteration loop, API backoff), `state.sh` → `loop_state.py` (state I/O, token tracking), `prompt.sh` → `loop_prompt.py` (prompt assembly), `tasks.sh` → `loop_tasks.py` (task detection). CLI: `set-orch-core loop *` subcommand group.

2. **Hook pipeline (`lib/hooks/` → `lib/set_hooks/`)**: New Python package, separate from `set_orch` because hooks have different lifecycle (called by Claude Code, not orchestrator). Five modules: `events.py` (event handlers), `stop.py` (metrics/transcript), `memory_ops.py` (recall/proactive), `session.py` (dedup cache), `util.py` (debug/timing).

3. **Hook startup latency**: Hooks run on every Claude tool use. Python startup (~50-80ms) is acceptable because:
   - Current bash hooks already take 50-200ms (calling `set-memory` which is Python)
   - The heavy path (memory recall) is already Python via `set-memory` CLI
   - Can use `#!/usr/bin/env python3` shebang directly, no bash wrapper overhead
   - Future optimization: persistent daemon if latency becomes an issue

4. **bin/wt-loop stays bash**: The entry point script (`bin/wt-loop`, 842 LOC) handles arg parsing, worktree path resolution, and `gnome-terminal`/`tmux` session management. This is shell-native work. The script calls the Python loop engine for the actual iteration logic. Same pattern as `bin/set-orchestrate` after Phase 8.

5. **bin/set-memory-hooks replacement**: Currently 772 LOC bash that sources `lib/hooks/*.sh` and dispatches by event type. Replace the dispatch logic with a Python entry point: `python3 -m lib.set_hooks.main "$EVENT" "$INPUT_FILE"`. Keep minimal bash wrapper for environment setup.

6. **Shared state format**: Loop state files (`loop-state.json`, `activity.json`) and hook cache files keep their current JSON format. No schema changes.

## Risks / Trade-offs

- **Hook latency regression**: If Python import time regresses, every Claude tool use slows down. Mitigation: benchmark before/after, keep imports minimal in hot path, lazy-import heavy modules.
- **Loop process management**: The loop engine manages `claude` CLI subprocesses via `script(1)` PTY wrapper. Python's `subprocess` + `pty` module can replicate this but needs careful testing for edge cases (signal handling, terminal size).
- **bin/wt-loop complexity**: The entry point does a lot of shell-specific work (terminal detection, tmux/gnome-terminal spawning, backgrounding). Keeping it bash is pragmatic but means the migration isn't "complete" for the loop subsystem. Acceptable trade-off — these are shell concerns.
- **lib/set_hooks as new package**: Adds a new top-level Python package. Must ensure it's importable from `bin/set-memory-hooks` (PYTHONPATH setup in the wrapper).
