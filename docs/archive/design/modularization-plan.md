# set-core Modularization Plan

Status: COMPLETED (2026-03-07)
Context: Explore session analysis of all major source files

## Problem

Several core scripts were monolithic (1000-3700 lines), making them hard to maintain, test, and develop. The largest offenders:

| File | Before | After | Reduction |
|------|--------|-------|-----------|
| bin/set-memory | 3,713 | 377 | 90% → lib/memory/ (7 modules) |
| bin/set-loop | 2,248 | 832 | 63% → lib/loop/ (4 modules) |
| bin/set-hook-memory | 1,817 | 55 | 97% → lib/hooks/ (5 modules) |
| lib/orchestration/state.sh | 1,597 | 794 | 50% → config.sh, utils.sh, orch-memory.sh |
| lib/orchestration/dispatcher.sh | 1,456 | 952 | 35% → builder.sh, monitor.sh |
| bin/set-project | 1,224 | 995 | 19% → lib/project/deploy.sh |
| bin/set-common.sh | 990 | 515 | 48% → lib/editor.sh |

## Approach

- Extract logical modules into `lib/` subdirectories
- Main scripts become thin dispatchers that `source` lib files
- Backward compatible — no CLI changes, no behavior changes
- Each extracted module gets unit tests

## Completed Phases

### Phase 1: set-common.sh editor extract ✅

Extracted 19 editor functions (497 lines) to `lib/editor.sh`. set-common.sh auto-sources it for backward compatibility. 4 editor-using scripts work unchanged.

### Phase 2: set-memory split ✅

```
bin/set-memory              (377)  infra + dispatcher + main()
lib/memory/core.sh        (1001)  remember, recall, proactive, list, get, forget, export, import
lib/memory/maintenance.sh  (743)  stats, cleanup, audit, dedup, verify, consolidation, graph_stats
lib/memory/rules.sh        (241)  rules YAML add/list/remove/match
lib/memory/todos.sh        (275)  todo add/list/done/clear
lib/memory/sync.sh         (384)  git-based sync push/pull/status
lib/memory/migrate.sh      (222)  migration framework
lib/memory/ui.sh           (482)  metrics, tui, dashboard, seed
```

### Phase 3: set-hook-memory split ✅

```
bin/set-hook-memory          (55)  thin dispatcher
lib/hooks/util.sh          (154)  logging, timers, root resolution
lib/hooks/session.sh       (134)  session cache, dedup, context IDs
lib/hooks/memory-ops.sh    (372)  recall, proactive, output formatting
lib/hooks/events.sh        (727)  9 event handlers
lib/hooks/stop.sh          (410)  transcript extraction, metrics flush
```

### Phase 4: Orchestration refactor ✅

```
lib/orchestration/config.sh       (52)  config/path lookup (from state.sh)
lib/orchestration/utils.sh       (649)  duration, hashing, parsing (from state.sh)
lib/orchestration/orch-memory.sh (114)  orch_remember/recall (from state.sh)
lib/orchestration/state.sh       (794)  jq state operations (core, kept name)
lib/orchestration/builder.sh     (151)  BASE_BUILD health (from dispatcher.sh)
lib/orchestration/monitor.sh     (358)  monitor_loop (from dispatcher.sh)
lib/orchestration/dispatcher.sh  (952)  dispatch/resume/pause (kept name)
```

Note: Task 5.8 (merger.sh BASE_BUILD dedup) was skipped — too tightly coupled for safe extraction.

### Phase 5: set-loop split ✅

```
bin/set-loop                (832)  CLI commands + main()
lib/loop/state.sh          (209)  state JSON, token accounting
lib/loop/tasks.sh          (236)  task detection (3 modes + manual tasks)
lib/loop/prompt.sh         (231)  prompt generation, change detection
lib/loop/engine.sh         (763)  cmd_run() iteration loop
```

### Phase 6: set-project deploy refactor ✅

```
bin/set-project             (995)  cmd_init + dispatch (from 1224)
lib/project/deploy.sh      (253)  _deploy_hooks, _deploy_commands, _deploy_skills, _deploy_mcp, _deploy_memory
```

## Test Coverage

| Test file | Tests | What it covers |
|-----------|-------|----------------|
| tests/unit/test_helpers.sh | 6 | Test framework self-test |
| tests/unit/test_editor.sh | 3 | Editor detection functions |
| tests/unit/test_memory_sync.sh | 3 | Sync state helpers |
| tests/unit/test_memory_migrate.sh | 3 | Migration framework |
| tests/unit/test_hook_session.sh | 2 | Dedup keys, context IDs |
| tests/unit/test_orch_state.sh | 5 | Duration parsing, hashing, config |
| tests/unit/test_loop_tasks.sh | 9 | Task detection, done criteria, change actions |

## What was NOT touched (by design)

- **set-sentinel** (390 lines) — already well-modularized
- **events.sh** (155 lines) — foundational, pure, zero coupling
- **gui/** — already uses mixins pattern
- **MCP server** — single file, simpler deployment

## Implementation rules

When working on any of the modularized files:
1. Check this plan for the target structure
2. Extract the relevant module FIRST, then make your feature/fix change
3. Keep the main script as a thin dispatcher
4. Add unit tests for the extracted module
5. Run existing integration tests to verify no regressions
