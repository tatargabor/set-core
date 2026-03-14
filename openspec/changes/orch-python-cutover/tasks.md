## 1. Python Monitor Loop — Fill Gaps

- [ ] 1.1 Add `send_summary_email()` to `lib/wt_orch/notifications.py` — HTML email with state summary + coverage results via Resend API
- [ ] 1.2 Add `trigger_checkpoint()` to `lib/wt_orch/engine.py` — set state status to "checkpoint", log reason, emit CHECKPOINT event
- [ ] 1.3 Add `final_coverage_check()` to `lib/wt_orch/digest.py` — read digest requirements JSON, compute covered/uncovered counts, return summary string
- [ ] 1.4 Add `update_coverage_status()` to `lib/wt_orch/digest.py` — update requirement coverage after merge (mark mapped requirements as covered)
- [ ] 1.5 Add `orch_memory_audit()` to `lib/wt_orch/orch_memory.py` — periodic memory health check (dedup dry-run + spot-check)
- [ ] 1.6 Wire watchdog heartbeat into Python monitor loop — call `event_bus.emit("WATCHDOG_HEARTBEAT")` at end of each poll cycle
- [ ] 1.7 Wire periodic memory operations into Python monitor loop — call `orch_memory_stats()`, `orch_gate_stats()`, `orch_memory_audit()` every ~10 polls
- [ ] 1.8 Wire notification calls into Python monitor loop — `send_notification()` at completion, partial completion, time limit; `send_summary_email()` at terminal states
- [ ] 1.9 Wire `final_coverage_check()` into Python monitor loop — call before marking done, include in summary email
- [ ] 1.10 Wire `trigger_checkpoint()` into Python monitor loop — periodic checkpoint and token hard limit triggers

## 2. Python Monitor Loop — Signal Handling & CLI

- [ ] 2.1 Add `cleanup_orchestrator()` function to `lib/wt_orch/engine.py` — update state to "stopped" (unless "done"), kill dev server PIDs, pause running changes if directive set
- [ ] 2.2 Register signal handlers in Python monitor entry point — SIGTERM, SIGINT, SIGHUP → call `sys.exit(0)` which triggers atexit cleanup
- [ ] 2.3 Register `cleanup_orchestrator()` via `atexit.register()` in monitor entry point
- [ ] 2.4 Add `wt-orch-core engine monitor` CLI subcommand to `lib/wt_orch/cli.py` — accept `--directives`, `--state`, `--poll-interval` args, call `engine.monitor_loop()`

## 3. Feature Flag & cmd_start() Cutover

- [ ] 3.1 Add `ORCH_ENGINE` env var check to `cmd_start()` in `lib/orchestration/dispatcher.sh` — if "python" (or default after cutover), exec to `wt-orch-core engine monitor` instead of calling bash `monitor_loop()`
- [ ] 3.2 Handle resume path in `cmd_start()` — when resuming from stopped/time_limit state with ORCH_ENGINE=python, perform recovery steps then exec to Python
- [ ] 3.3 Pass dispatch-critical globals as CLI args to Python monitor — `--default-model`, `--team-mode`, `--context-pruning`, `--model-routing`, `--checkpoint-auto-approve`

## 4. Python Merge Pipeline — Fill Gaps

- [ ] 4.1 Add hook execution to `lib/wt_orch/merger.py:merge_change()` — call pre_merge and post_merge hooks via `subprocess_utils.run_command()`
- [ ] 4.2 Add `_sync_running_worktrees()` to `lib/wt_orch/merger.py` — after merge, iterate running changes and call `dispatcher.sync_worktree_with_main()` for each
- [ ] 4.3 Wire `digest.update_coverage_status()` into `merger.py:merge_change()` — call after successful merge to update requirement coverage
- [ ] 4.4 Wire `builder.fix_base_build()` into `merger.py:merge_change()` — call when post-merge build check fails
- [ ] 4.5 Add conflict fingerprint dedup to `merger.py:_try_merge()` — track MD5 of conflicting files, skip already-seen conflicts
- [ ] 4.6 Wire Python `merge_change()` and `retry_merge_queue()` into `engine.py` monitor loop — replace bash subprocess calls with direct Python function imports

## 5. Python Auto-Replan — Eliminate Circular Dependency

- [ ] 5.1 Implement `auto_replan_cycle()` fully in `lib/wt_orch/engine.py` — collect replan context, archive completed changes, call Claude for new plan, validate, dispatch
- [ ] 5.2 Replace bash `auto_replan_cycle` shell-out in `engine.py:_handle_auto_replan()` — call `planner.collect_replan_context()` and `planner.build_decomposition_context()` directly
- [ ] 5.3 Add Claude invocation to Python replan — use `subprocess_utils.run_claude()` with decomposition prompt, parse JSON response
- [ ] 5.4 Add novelty check to Python replan — compare new plan changes against previously failed changes, return "no new work" if all duplicates
- [ ] 5.5 Add state archival to Python replan — archive completed changes to `state-archive.jsonl` before generating new plan

## 6. Python Planning Orchestration

- [ ] 6.1 Add `run_planning_pipeline()` to `lib/wt_orch/planner.py` — orchestrate full flow: input detection, freshness check, triage gate, design bridge, Claude call, response parse, plan enrichment
- [ ] 6.2 Add design bridge support to Python planning — detect design MCP, fetch snapshot, include design tokens in decomposition prompt
- [ ] 6.3 Wire triage gate into Python planning — call `check_triage_gate()`, handle auto-defer in automated mode
- [ ] 6.4 Add `populate_coverage()` to `lib/wt_orch/digest.py` — map plan changes to digest requirements
- [ ] 6.5 Add `check_coverage_gaps()` to `lib/wt_orch/digest.py` — warn about uncovered requirements after plan creation

## 7. Bash Cleanup — Remove Dead Code

- [ ] 7.1 Delete bash `monitor_loop()` from `lib/orchestration/monitor.sh` — keep only the file header comment pointing to Python
- [ ] 7.2 Delete bash `merge_change()` and `retry_merge_queue()` from `lib/orchestration/merger.sh` — keep only delegated wrappers (archive, cleanup-all)
- [ ] 7.3 Delete bash `auto_replan_cycle()` from `lib/orchestration/planner.sh` — keep `cmd_plan()` wrapper for CLI use
- [ ] 7.4 Remove dead Python code in `engine.py:_handle_auto_replan()` — the bash shell-out (line 543-544) that creates circular dependency
- [ ] 7.5 Update `lib/orchestration/monitor.sh` header comment — "monitor_loop runs in Python via wt-orch-core engine monitor"
- [ ] 7.6 Update `lib/orchestration/merger.sh` header comment — "merge_change runs in Python, this file has thin wrappers only"

## 8. Validation

- [ ] 8.1 Test `ORCH_ENGINE=python wt-orchestrate start` on a small project — verify Python monitor starts, polls, dispatches, merges, and completes
- [ ] 8.2 Test signal handling — send SIGTERM/SIGINT to Python monitor, verify cleanup_orchestrator runs and state is "stopped"
- [ ] 8.3 Test `ORCH_ENGINE=bash wt-orchestrate start` still works — backward compatibility
- [ ] 8.4 Run full minishop orchestration with Python engine — validate auto-replan, merge, coverage, notifications
- [ ] 8.5 Flip default `ORCH_ENGINE` to "python" after validation
