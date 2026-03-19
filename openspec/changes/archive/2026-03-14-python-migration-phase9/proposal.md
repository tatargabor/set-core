## Why

Phase 9 of the Python migration. After Phase 8 completes the orchestration engine, two major bash subsystems remain: the Ralph loop engine (`lib/loop/*`, 2,398 LOC) and the Claude Code hook pipeline (`lib/hooks/*`, 1,822 LOC). The loop engine is a complex state machine managing worktree agent iterations with API backoff, token budgets, and stall detection — all patterns where Python's structured error handling and typing are superior. The hooks pipeline runs on every Claude tool use and manages memory recall, frustration detection, and transcript extraction — latency-sensitive but logic-heavy code that benefits from Python's JSON/string processing.

## What Changes

- **New `lib/set_orch/loop.py`** (~500 LOC): 1:1 migration of `lib/loop/engine.sh` (903 LOC) — main iteration loop, API error classification/backoff, iteration lifecycle, completion detection, token budget enforcement
- **New `lib/set_orch/loop_prompt.py`** (~200 LOC): 1:1 migration of `lib/loop/prompt.sh` (305 LOC) — change action detection, Claude prompt assembly, context injection
- **New `lib/set_orch/loop_state.py`** (~150 LOC): 1:1 migration of `lib/loop/state.sh` (255 LOC) — loop state file management, token tracking, date parsing
- **New `lib/set_orch/loop_tasks.py`** (~150 LOC): 1:1 migration of `lib/loop/tasks.sh` (235 LOC) — task file detection, completion checking, manual task handling
- **New `lib/set_hooks/events.py`** (~400 LOC): 1:1 migration of `lib/hooks/events.sh` (727 LOC) — SessionStart, UserPrompt, PostTool event handlers, cheat sheet recall, project context injection
- **New `lib/set_hooks/stop.py`** (~250 LOC): 1:1 migration of `lib/hooks/stop.sh` (420 LOC) — metrics flush, transcript extraction, commit-based memory save
- **New `lib/set_hooks/memory_ops.py`** (~230 LOC): 1:1 migration of `lib/hooks/memory-ops.sh` (393 LOC) — recall, proactive context, rules matching, output formatting
- **New `lib/set_hooks/session.py`** (~100 LOC): 1:1 migration of `lib/hooks/session.sh` (134 LOC) — dedup cache, context ID generation
- **New `lib/set_hooks/util.py`** (~80 LOC): 1:1 migration of `lib/hooks/util.sh` (148 LOC) — debug logging, timing, cache I/O
- **Delete all `lib/loop/*.sh` and `lib/hooks/*.sh`** after migration
- **Update `bin/wt-loop`** to call Python loop engine
- **Update `bin/set-memory-hooks`** (or replace) to call Python hook handlers
- Unit tests for all new modules

## Capabilities

### New Capabilities
- `ralph-loop-engine`: Main iteration loop with API error backoff, token budget, completion detection, stall recovery, iteration lifecycle management
- `ralph-loop-prompt`: Change action detection (ff/apply/done), Claude prompt assembly, spec context injection, permission flag resolution
- `ralph-loop-state`: Loop state file I/O, token tracking, date parsing, iteration metadata
- `ralph-loop-tasks`: Task file discovery, completion percentage, manual task detection, done criteria
- `hook-event-handlers`: SessionStart (cheat sheet + project context), UserPrompt (topic recall), PostTool (commit save, error context), event routing
- `hook-stop-pipeline`: Metrics flush, transcript extraction, raw insight filtering, commit-based memory save
- `hook-memory-ops`: Memory recall, proactive context retrieval, rules.yaml matching, output formatting with dedup
- `hook-session-utils`: Dedup cache management, context ID generation, content hash tracking

### Modified Capabilities

## Impact

- **Deleted**: All files in `lib/loop/*.sh` (4 files, 2,398 LOC) and `lib/hooks/*.sh` (5 files, 1,822 LOC)
- **New package**: `lib/set_hooks/` (5 modules) — new Python package for hook handlers
- **New modules**: `lib/set_orch/loop.py`, `loop_prompt.py`, `loop_state.py`, `loop_tasks.py`
- **Modified**: `bin/wt-loop` — rewritten to call Python
- **Modified**: `bin/set-memory-hooks` — rewritten to call Python
- **Tests**: `test_loop.py`, `test_loop_prompt.py`, `test_hook_events.py`, `test_hook_stop.py`
- **Performance concern**: Hook handlers run on every tool use. Python startup latency (~50ms) must be managed — either persistent process, or pre-import optimization. May need to keep a thin bash dispatcher that calls Python only for heavy operations.
- **Dependencies**: No new external deps
