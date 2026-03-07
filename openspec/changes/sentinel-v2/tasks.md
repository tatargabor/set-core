## 1. Module Extraction (mechanical refactor)

- [x] 1.1 Create `lib/orchestration/` directory
- [x] 1.2 Extract `lib/orchestration/state.sh` — move `init_state`, `update_state_field`, `update_change_field`, `get_change_status`, `get_changes_by_status`, `count_changes_by_status`, `deps_satisfied`, `topological_sort`, `generate_summary`, `trigger_checkpoint`, `brief_hash`, `load_config_file`, `resolve_directives`, `parse_directives`, `parse_next_items`, `find_brief`, `find_input`, `find_openspec_dir`, `parse_duration`, `any_loop_active`, `format_duration`, `send_notification`, `orch_remember`, `orch_recall`, `orch_memory_stats`, `orch_memory_audit`, `orch_gate_stats`, `cmd_status`, `cmd_approve`
- [x] 1.3 Extract `lib/orchestration/planner.sh` — move `cmd_plan`, `validate_plan`, `check_scope_overlap`, `summarize_spec`, `estimate_tokens`, `detect_test_infra`, `auto_detect_test_command`, `auto_replan_cycle`, `cmd_replan`
- [x] 1.4 Extract `lib/orchestration/dispatcher.sh` — move `dispatch_change`, `dispatch_ready_changes`, `resume_stopped_changes`, `resume_change`, `pause_change`, `resume_stalled_changes`, `retry_failed_builds`, `resolve_change_model`, `bootstrap_worktree`, `sync_worktree_with_main`, `check_base_build`, `fix_base_build_with_llm`, `cmd_start`, `cmd_pause`, `cmd_resume`, `monitor_loop`
- [x] 1.5 Extract `lib/orchestration/verifier.sh` — move `poll_change`, `handle_change_done`, `run_tests_in_worktree`, `review_change`, `verify_merge_scope`, `extract_health_check_url`, `health_check`, `smoke_fix_scoped`. Convert `smoke_command`, `smoke_timeout`, `smoke_blocking` from `monitor_loop()` local closures to explicit function arguments — these variables are accessed by verifier functions but declared local in dispatcher's `monitor_loop()`
- [x] 1.6 Extract `lib/orchestration/merger.sh` — move `merge_change`, `cleanup_worktree`, `cleanup_all_worktrees`, `execute_merge_queue`, `retry_merge_queue`, `_try_merge`, `archive_change`
- [x] 1.7 Reduce `bin/wt-orchestrate` to thin wrapper — keep constants, logging, `model_id`, `rotate_log`, `cmd_self_test`, `usage`, `main`; add `source` statements for all modules. Source order must match design D1: `events.sh` first (other modules emit events), then `state.sh`, `watchdog.sh`, `planner.sh`, `dispatcher.sh`, `verifier.sh`, `merger.sh`
- [x] 1.8 Verify `cmd_self_test` passes after extraction — all functions callable, no missing variables
- [x] 1.9 Migrate existing `stall_count` detection in `poll_change()` to watchdog infrastructure — remove legacy stall logic, prevent dual-detection conflicts with new watchdog

## 2. Events System

- [x] 2.1 Create `lib/orchestration/events.sh` with `emit_event(type, change_name, data)` — append JSONL to `orchestration-events.jsonl`. Include `trace_id` field (per-change, set at dispatch) and `span_id` field (per-operation) in schema for future observability
- [x] 2.2 Implement event log rotation — archive at `events_max_size` (1MB default), keep last 3 archives
- [x] 2.3 Hook `update_change_field()` in state.sh for automatic `STATE_CHANGE` emission on status field changes
- [x] 2.4 Hook token tracking for automatic `TOKENS` event emission on `tokens_used` updates
- [x] 2.5 Add `DISPATCH` event emission in `dispatch_change()`
- [x] 2.6 Add `MERGE_ATTEMPT` event emission in `merge_change()` / `_try_merge()`
- [x] 2.7 Add `VERIFY_GATE` event emission in `handle_change_done()` for test/build/review/smoke results
- [x] 2.8 Add `REPLAN` event emission in `auto_replan_cycle()`
- [x] 2.9 Add `CHECKPOINT` event emission in `trigger_checkpoint()`
- [x] 2.10 Add `ERROR` event emission for error conditions
- [x] 2.11 Add `events_log`, `events_max_size` directives to `parse_directives()`. Only emit `TOKENS` events on significant deltas (>10K tokens change) to reduce I/O overhead
- [x] 2.12 Implement `cmd_events()` subcommand — `wt-orchestrate events` with `--type`, `--change`, `--since`, `--last N`, `--json` filters
- [x] 2.13 Implement event-based auto run report in `generate_summary()` — markdown summary from events at orchestration completion

## 3. Watchdog

- [x] 3.1 Create `lib/orchestration/watchdog.sh` with `watchdog_check(change_name)` function
- [x] 3.2 Implement per-state timeout detection — track `last_activity_epoch`, check loop-state.json mtime, verify Ralph PID is dead before triggering
- [x] 3.3 Implement action hash loop detection — compute MD5 of `(loop-state mtime, tokens_used, ralph_status)`, maintain ring buffer, detect consecutive identical hashes
- [x] 3.4 Implement escalation chain — levels 0-4 with persist per change, reset on successful activity
- [x] 3.5 Implement `watchdog_heartbeat()` — emit `WATCHDOG_HEARTBEAT` event every poll cycle
- [x] 3.6 Emit `WATCHDOG_WARN`, `WATCHDOG_RESUME`, `WATCHDOG_KILL`, `WATCHDOG_FAILED` events at each escalation level
- [x] 3.7 Add watchdog state storage in `orchestration-state.json` per change (`watchdog` sub-object)
- [x] 3.8 Hook `watchdog_check()` into `monitor_loop()` after each `poll_change()` call
- [x] 3.9 Hook `watchdog_heartbeat()` at end of each poll cycle in `monitor_loop()`
- [x] 3.10 Add `watchdog_timeout` and `watchdog_loop_threshold` directives to `parse_directives()`
- [x] 3.11 Implement per-change token budget enforcement — `max_tokens_per_change` directive (default: 2M). Watchdog checks `tokens_used` each poll: warn at 80%, pause at 100%, fail at 120%. Complexity-based defaults: S=500K, M=2M, L=5M, XL=10M
- [x] 3.12 Implement partial work salvage on failure — before marking change `failed`, capture `git diff` from worktree, save as `partial-diff.patch` in change state, record modified files list. Dispatcher can provide patch as "previous progress" context on retry/replan

## 4. Worktree Context Pruning

- [x] 4.1 Implement `prune_worktree_context()` in dispatcher.sh — remove `.claude/commands/wt/orchestrate*.md`, `sentinel*.md`, `manual*.md` from worktree
- [x] 4.2 Add `context_pruning` directive to `parse_directives()` (default: true)
- [x] 4.3 Call `prune_worktree_context()` from `bootstrap_worktree()` after worktree setup, before dispatch
- [x] 4.4 Log count of pruned files — no error on empty glob match
- [x] 4.5 Verify preservation — negative test that `.claude/rules/`, `.claude/skills/`, `CLAUDE.md`, and `loop*.md` survive pruning

## 5. Project Knowledge System

- [x] 5.1 Create template `templates/project-knowledge.yaml` with version header, cross_cutting_files, features, verification_rules sections
- [x] 5.2 Create template `templates/cross-cutting-checklist.md` with path-scoped frontmatter and placeholder checklist items
- [x] 5.3 Implement `wt-project init-knowledge` subcommand — scan project for dashboard pages, i18n files, sidebar, activity logger patterns
- [x] 5.4 Generate draft `project-knowledge.yaml` from scan results — user reviews and commits

## 6. Planner Enhancements

- [x] 6.1 Enhance `check_scope_overlap()` — read `cross_cutting_files` from project-knowledge.yaml, detect file-path overlap between parallel changes
- [x] 6.2 Inject merge hazard analysis into `cmd_plan()` decompose prompt when project-knowledge.yaml exists
- [x] 6.3 Enhance `auto_replan_cycle()` — inject git log of completed changes and their file lists into replanner prompt to prevent duplication
- [x] 6.4 Add `plan_approval` directive (default: false). When true, orchestrator enters `plan_review` status after plan generation — user must `wt-orchestrate approve` before dispatch begins

## 7. Per-Change Model Routing

- [x] 7.1 Add `model_routing` directive to `parse_directives()` (values: `off` | `complexity`, default: `off`)
- [x] 7.2 Enhance `resolve_change_model()` — three-tier priority: explicit per-change model > complexity-based routing > default_model directive
- [x] 7.3 Implement complexity-based routing logic — S-complexity non-feature changes route to sonnet when `model_routing: complexity`
- [x] 7.4 Add `review_model` directive — configurable model for review gate. Implement Sonnet→Opus auto-escalation: if Sonnet review fails/timeouts, retry with Opus without counting as a verify failure

## 8. Verifier Enhancements

- [x] 8.1 Implement `evaluate_verification_rules()` — read rules from project-knowledge.yaml, evaluate triggers against `git diff`
- [x] 8.2 Hook verification rules into `handle_change_done()` — run after tests/build pass, before merge
- [x] 8.3 Report verification results — errors block merge, warnings logged and included in verify gate result
- [x] 8.4 Graceful degradation — all verification no-ops when project-knowledge.yaml absent
- [x] 8.5 Add `merge-blocked` change state — when merge fails (LLM resolver output empty), mark as `merge-blocked` instead of crashing. Orchestrator continues with other changes, operator can manually resolve and `wt-orchestrate approve <name>`

## 9. Enhanced Sentinel

- [x] 9.1 Replace `wait $child_pid` with polling loop in `bin/wt-sentinel` — `kill -0` check with sleep interval
- [x] 9.2 Implement `check_orchestrator_liveness()` — monitor `orchestration-events.jsonl` mtime, detect no-activity for `sentinel_stuck_timeout` (180s default)
- [x] 9.3 Implement controlled restart with exponential backoff — SIGTERM, wait 30s, SIGKILL if still alive, fix stale state (set status=stopped). Backoff: 30s→60s→120s→240s with 0-25% jitter between restart attempts
- [x] 9.4 Emit `SENTINEL_RESTART` event — implement inline JSONL append in wt-sentinel (no dependency on events.sh sourcing, just direct echo >> events.jsonl)
- [x] 9.5 Add `sentinel_stuck_timeout` to sentinel configuration
- [x] 9.6 Classify failures as transient (PID died, API timeout) vs permanent (test failures, scope violation) — only auto-retry transient failures. Add `max_retries_per_change` directive (default: 3)

## 10. Dispatcher Enhancements

- [x] 10.1 Implement targeted context injection in `dispatch_change()` — read feature's `touches` list from project-knowledge.yaml, inject cross-cutting file context into change proposal
- [x] 10.2 Include reference implementation path in dispatch context when feature has `reference_impl: true`
- [x] 10.3 Implement `dispatch_backend` abstraction — `dispatch_change()` calls a backend-specific function (`dispatch_via_wt_loop` for current, future `dispatch_via_agent_teams`). Default: `wt-loop`. Interface: backend receives change name, model, worktree path, prompt; returns PID
- [x] 10.4 Inject sibling status summary at dispatch time — list of other active changes with their file scopes, so agents are aware of parallel work and can avoid conflicts

## 11. Quality Gate Hooks

- [x] 11.1 Add orchestration lifecycle hook points: `pre_dispatch`, `post_verify`, `pre_merge`, `post_merge`, `on_fail` — each an optional shell script path in `orchestration.yaml`
- [x] 11.2 Hook receives change name, status, worktree path as arguments. Non-zero exit blocks the transition, stderr logged as reason
- [x] 11.3 Add `hooks` section to `parse_directives()` — map of hook name to script path

## 12. Crash-Safe State Recovery

- [x] 12.1 Implement `reconstruct_state_from_events()` — rebuild `orchestration-state.json` from `orchestration-events.jsonl` by replaying state transitions
- [x] 12.2 Sentinel calls `reconstruct_state_from_events()` on startup if state appears inconsistent (running change with no PID, or state mtime older than events mtime)

## 13. Consumer Project Migration

- [x] 13.1 Store wt-tools version in consumer project — `wt-project init` writes `.claude/.wt-version` (git short hash or semver tag). On subsequent runs, compare stored vs current version to detect drift
- [x] 13.2 Enhance `wt-project init` with migration logic — when stored version is older than current:
  - Merge new directives into `orchestration.yaml` (additive only, never overwrite existing values)
  - Scaffold `project-knowledge.yaml` via `init-knowledge` if missing
  - Deploy `cross-cutting-checklist.md` rule template if missing
  - Report summary: "Updated from <old> to <new>: added N directives, created M new files"
- [x] 13.3 Add `wt-project init --dry-run` flag — show what would change without modifying files
- [x] 13.4 Directive schema validation — warn if consumer's `orchestration.yaml` has unknown or deprecated directives after migration

## 14. Documentation

- [x] 14.1 Create `docs/project-management.md` — consumer project lifecycle guide covering: initial setup (`wt-project init`), version tracking (`.wt-version`), migration on update, `--dry-run` preview, directive schema reference
- [x] 14.2 Document `project-knowledge.yaml` format — schema reference with all fields, example entries, how planner/dispatcher/verifier use it, `init-knowledge` scaffolding workflow
- [x] 14.3 Document `orchestration.yaml` directive reference — all directives (existing + new sentinel-v2 ones) with types, defaults, and examples. Include watchdog, events, hooks, model routing, token budgets sections
- [x] 14.4 Document orchestration event types — `orchestration-events.jsonl` format, all event types with example payloads, `wt-orchestrate events` query usage
- [x] 14.5 Add troubleshooting section — common scenarios: stuck orchestrator (watchdog handles), merge-blocked (manual resolve + approve), token budget exceeded, state reconstruction from events

## 15. Integration Testing

- [x] 15.1 Run `cmd_self_test` with all sourced modules — verify function availability and basic operations
- [x] 15.2 Test event emission — emit events, verify JSONL format, test rotation, verify trace_id/span_id fields
- [x] 15.3 Test watchdog — simulate stuck change (dead PID + stale mtime), verify escalation chain including per-change token budget enforcement
- [x] 15.4 Test context pruning — create worktree, verify orchestrator commands removed, agent-essential files preserved
- [x] 15.5 Test verification rules — create mock project-knowledge.yaml, verify rule evaluation against git diff
- [x] 15.6 Test partial work salvage — simulate failed change, verify diff captured and available for retry
- [x] 15.7 Test merge-blocked state — simulate LLM resolver failure, verify orchestrator continues with other changes
- [x] 15.8 Test state reconstruction — corrupt state.json, verify reconstruction from events.jsonl
- [x] 15.9 Test quality gate hooks — verify hook execution, blocking, and error reporting
- [x] 15.10 Test consumer migration — deploy to consumer project via `wt-project init`, verify version tracking, directive merge, and no regressions
