## Context

The orchestration system was migrated from bash to Python in stages. The "heavy lifting" functions (dispatch, verify, poll, report) were migrated first and the bash versions became thin wrappers calling `wt-orch-core <subcommand>`. However, the "control plane" functions — the monitor loop, merge pipeline, planning orchestration, and auto-replan cycle — remained as full bash implementations.

During migration, Python clean-room reimplementations were written for these too (`engine.py`, `merger.py`), but they were never wired in. The bash versions continue to run, creating ~2500 lines of maintained-but-dead Python code and a dual-maintenance burden for every bug fix.

Current call chain:
```
wt-orchestrate start → cmd_start() [bash]
  → monitor_loop() [bash, 590 LOC]
    → poll_change() → wt-orch-core [python ✓]
    → dispatch_ready() → wt-orch-core [python ✓]
    → merge_change() [bash, 420 LOC — NOT delegated]
    → watchdog_check() → wt-orch-core [python ✓]
    → auto_replan_cycle() [bash, 170 LOC — NOT delegated]
    → completion logic [bash, 150 LOC — duplicated in engine.py]
```

## Goals / Non-Goals

**Goals:**
- Eliminate bash↔Python duplication — one source of truth for each function
- Make Python `engine.py:monitor_loop()` the live orchestration engine
- Make Python `merger.py:merge_change()` the live merge pipeline
- Move auto-replan and planning orchestration fully to Python
- Reduce bash `.sh` files to thin entry-point wrappers (signal traps, exec)
- Maintain 100% behavioral compatibility — no externally visible changes

**Non-Goals:**
- Rewriting `wt-loop` (PTY management stays in bash — fundamentally different concern)
- Changing the `wt-orchestrate` CLI interface
- Migrating `cmd_digest()` entry point (too large, defer to follow-up)
- Removing `dispatcher.sh` entirely — `cmd_start()` stays bash for signal traps

## Decisions

### D1: Phased cutover via feature flag, not big-bang

**Decision**: Add a `ORCH_ENGINE=python` env var (default: `bash` initially). `cmd_start()` checks this and either calls bash `monitor_loop()` or `wt-orch-core engine monitor`. After validation, flip default to `python` and remove bash monitor_loop().

**Why**: A big-bang switch is too risky for the core orchestration loop. The feature flag allows running a test orchestration with Python, comparing results, and reverting instantly if something breaks.

**Alternative rejected**: Gradual function-by-function delegation (current approach) — led to the duplication problem in the first place.

### D2: Python monitor_loop() calls Python functions directly, not via wt-orch-core CLI

**Decision**: When running in Python mode, `engine.py:monitor_loop()` imports and calls `merger.merge_change()`, `dispatcher.dispatch_ready_changes()`, etc. as Python function calls — not by shelling out to `wt-orch-core`.

**Why**: The whole point is eliminating bash subprocess overhead and having a single-process orchestrator. The `wt-orch-core` CLI is for bash→Python bridging; Python→Python should be direct imports.

### D3: Signal handling via Python signal module + atexit

**Decision**: `cmd_start()` (bash) does `exec wt-orch-core engine monitor ...` which replaces the bash process. Python registers SIGTERM/SIGINT/SIGHUP handlers and atexit cleanup.

**Why**: `exec` means bash exits and Python becomes PID — signal handling is clean. No zombie processes.

**Implementation**:
```python
import signal, atexit

def cleanup():
    # Update state to "stopped" (unless "done")
    # Kill dev server if auto-started
    # Pause running changes if pause_on_exit directive

atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))
```

### D4: Fill gaps by wiring existing Python modules, not reimplementing

**Decision**: Most "bash-only" functions already have Python equivalents in different modules. Wire them in rather than writing new code.

| Bash-only function | Python equivalent | Action needed |
|---|---|---|
| `send_notification()` | `notifications.py:send_notification()` | Already exists, just call it |
| `send_summary_email()` | `notifications.py` | Add `send_summary_email()` method |
| `orch_remember/recall()` | `orch_memory.py` | Already exists, just call it |
| `trigger_checkpoint()` | — | Add to `engine.py` (simple state update) |
| `watchdog_heartbeat()` | `events.py:emit()` | Emit WATCHDOG_HEARTBEAT event |
| `final_coverage_check()` | `digest.py` | Add function (reads digest JSON, checks coverage) |
| `update_coverage_status()` | `digest.py` | Add function (updates requirement status in digest) |
| `_sync_running_worktrees()` | `dispatcher.py:sync_worktree_with_main()` | Loop over running changes, call existing |
| `fix_base_build_with_llm()` | `builder.py:fix_base_build()` | Already exists |

### D5: auto_replan_cycle fully in Python, breaking the circular dependency

**Decision**: Move `auto_replan_cycle()` entirely to `engine.py` (or a new `replanner.py`). The Python version calls `planner.py:collect_replan_context()` and `planner.py:build_decomposition_context()` directly, then calls Claude via `subprocess_utils.run_claude()`.

**Why**: The current Python `_handle_auto_replan()` shells out to `bash planner.sh auto_replan_cycle()` which shells back to `wt-orch-core plan build-context` — absurd circular dependency.

### D6: merge_change() delegates hooks via subprocess, not Python reimplementation

**Decision**: Python `merger.py:merge_change()` runs user-defined hooks (pre_merge, post_merge) via `subprocess_utils.run_command()`. Hook scripts are bash by nature — no need to reimplement them in Python.

**Why**: Hooks are user-defined shell scripts. Calling them via subprocess is correct and matches how the bash version works.

## Risks / Trade-offs

**[Risk: Behavioral divergence during cutover]** → Mitigation: Feature flag (`ORCH_ENGINE=python|bash`) allows instant rollback. Run parallel test (minishop-run) with Python engine before flipping default.

**[Risk: Signal handling differences]** → Mitigation: Python `exec` replaces bash process, so signals go directly to Python. Test with SIGTERM, SIGINT, SIGHUP. `atexit` runs on normal exit; signal handlers call `sys.exit(0)` which triggers atexit.

**[Risk: Missing edge cases in Python monitor_loop()]** → Mitigation: The Python engine.py was written as a "clean-room" reimplementation. Diff it line-by-line against bash monitor.sh to find missing edge cases before cutover. Known gaps: memory audit, coverage, summary email.

**[Risk: Performance change]** → Mitigation: Python monitor loop does `load_state()` from disk on every poll (same as bash jq). No caching introduced, so same I/O pattern.

**[Risk: auto_replan_cycle migration complexity]** → Trade-off: This is the most complex migration. `auto_replan_cycle()` touches planning, state archival, dispatch, and coverage. Defer to Phase 3 and validate monitor+merge first.

## Migration Plan

### Phase 1: Monitor loop cutover
1. Fill Python gaps in `engine.py` (checkpoint, coverage, email, memory)
2. Add `wt-orch-core engine monitor` CLI handler with signal setup
3. Add `ORCH_ENGINE` feature flag to `cmd_start()`
4. Test with `ORCH_ENGINE=python wt-orchestrate start`
5. Validate with minishop-run
6. Flip default to `python`
7. Delete bash `monitor_loop()` from `monitor.sh`

### Phase 2: Merge pipeline cutover
1. Fill Python gaps in `merger.py` (coverage, sync, hooks)
2. Wire `merger.py:merge_change()` into engine.py monitor loop
3. Delete bash `merge_change()` and `retry_merge_queue()` from `merger.sh`

### Phase 3: Replan + planning cutover
1. Move `auto_replan_cycle()` fully to Python
2. Move `cmd_plan()` orchestration to Python
3. Delete bash orchestration from `planner.sh` (keep thin wrappers for CLI)

### Phase 4: Cleanup
1. Delete dead bash code from `monitor.sh`, `merger.sh`
2. Reduce remaining `.sh` files to thin wrappers
3. Update documentation

### Rollback
At any phase: set `ORCH_ENGINE=bash` to revert to bash monitor loop. Bash code is not deleted until the phase is validated.

## Open Questions

- Should `cmd_start()` itself move to Python eventually, or stay as bash entry point for signal traps? (Current decision: stay bash, use `exec`)
- Should `cmd_digest()` be included in this change or deferred? (Current decision: defer — it's 1500 LOC and mostly independent)
