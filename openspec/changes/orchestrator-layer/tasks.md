## 1. Project Brief Format

- [x] 1.1 Create `openspec/project-brief.md` template with Feature Roadmap section (Done/Next/Ideas subsections) and Orchestrator Directives section (max_parallel, merge_policy, checkpoint_every, test_command, notification, token_budget, pause_on_exit)
- [x] 1.2 Implement brief parser function in `bin/wt-orchestrate`: extract Next items (bullet list), parse directives (key: value format), compute SHA-256 hash, apply defaults for missing directives
- [x] 1.3 Add validation: error on missing brief, error on empty Next section, warning on invalid directive values with fallback to defaults

## 2. CLI Skeleton and State Management

- [x] 2.1 Create `bin/wt-orchestrate` with subcommand dispatch: plan, start, status, pause, resume, replan, approve — source wt-common.sh for shared functions
- [x] 2.2 Implement orchestration-state.json read/write functions: init_state, update_state, get_change_status, set_change_status — use jq for JSON manipulation (same pattern as wt-loop)
- [x] 2.3 Add `orchestration-state.json` to project `.gitignore`
- [x] 2.4 Implement `wt-orchestrate status` subcommand: read state file, display table with per-change name/status/progress/tokens, show merge queue, show brief staleness indicator
- [x] 2.5 Add orchestrator logging: append to `.claude/orchestration.log` with ISO 8601 timestamps for all state transitions, dispatch, merge, checkpoint, and error events
- [x] 2.6 Add log rotation: on startup, if `.claude/orchestration.log` exceeds 100KB, truncate keeping last 50KB
- [x] 2.7 Add cleanup trap (SIGTERM/SIGINT): update orchestration-state.json status to "stopped", log stop event, optionally pause all Ralph loops if `pause_on_exit` directive is true

## 3. Plan Generation (Decomposition)

- [x] 3.1 Implement `wt-orchestrate plan` subcommand: read brief, collect existing spec names from `openspec/specs/`, collect active changes from `openspec/changes/`, query `wt-memory recall` for top 5 relevant memories
- [x] 3.2 Build the Claude decomposition prompt: include brief content, existing spec list, active changes, memory context — ask for JSON output with change names, scopes, dependencies, complexity
- [x] 3.3 Invoke `claude -p "<prompt>" --output-format json` and parse response into `orchestration-plan.json` with plan_version, brief_hash, created_at, and changes array
- [x] 3.4 Implement `wt-orchestrate plan --show`: display plan in human-readable format with ASCII dependency graph (topological sort)
- [x] 3.5 Add plan validation: check for circular dependencies, verify all depends_on references exist, warn on changes that duplicate existing active changes

## 4. Change Dispatch

- [x] 4.1 Implement dispatch_change function: `wt-new <change-name>`, `openspec new change <name>` in worktree, pre-create `proposal.md` from plan scope (Why from roadmap_item, What Changes from scope), `wt-loop start --max 30 --done openspec`
- [x] 4.2 Implement dependency resolution: topological sort of change graph, dispatch only when all depends_on are in "merged" status, respect max_parallel limit
- [x] 4.3 Implement `wt-orchestrate start` subcommand: validate plan exists, initialize orchestration-state.json, dispatch all ready changes (no dependencies + under parallel limit)

## 5. Progress Monitor Loop

- [x] 5.1 Implement monitor loop in `wt-orchestrate start`: poll each active worktree's `.claude/loop-state.json` every 30 seconds, update orchestration-state.json with current iteration/tokens/status
- [x] 5.2 Handle completion: when Ralph status is "done", run test_command in worktree, then run verify step (`claude -p "Run /opsx:verify <change>" --max-turns 5` in worktree), transition to "done" (both pass) or restart Ralph for one retry (verify fails), then "failed" if retry also fails
- [x] 5.3 Handle stall/stuck: when Ralph status is "stalled" or "stuck", update change status, send notification, continue monitoring other changes
- [x] 5.4 After each status check cycle: call dispatch_ready_changes() to start any newly-unblocked changes
- [x] 5.5 Detect plan completion: all changes in "done" or "merged" status → trigger final checkpoint, set orchestration status to "done"

## 6. Auto-Merge Pipeline

- [x] 6.1 Implement merge_change function: dry-run conflict check (`git merge --no-commit --no-ff` + `git merge --abort`), run `wt-merge <change> --no-push`, run `wt-close <change>`, update state to "merged"
- [x] 6.2 Implement eager merge policy: call merge_change immediately when change is "done" + tests pass + no conflicts
- [x] 6.3 Implement checkpoint merge policy: add done changes to merge queue array in state, execute queue only on `wt-orchestrate approve --merge`
- [x] 6.4 Implement merge conflict detection: mark change as "merge-blocked", notify developer with conflicting file list
- [x] 6.5 Implement dependency unlock: after merge, scan pending changes and dispatch any whose depends_on are all "merged"

## 7. Pause, Resume, and Replan

- [x] 7.1 Implement `wt-orchestrate pause <change>`: read ralph-terminal.pid from worktree, send SIGTERM, update change status to "paused"
- [x] 7.2 Implement `wt-orchestrate pause --all`: iterate all running changes, pause each, set orchestration status to "paused"
- [x] 7.3 Implement `wt-orchestrate resume <change>`: cd to existing worktree, `wt-loop start --max 30 --done openspec`, update status to "running"
- [x] 7.4 Implement `wt-orchestrate resume --all`: resume all paused changes respecting max_parallel
- [x] 7.5 Implement `wt-orchestrate replan`: read current state + updated brief, call Claude with both (include done/active/pending info), write updated plan with incremented plan_version, preserve merged changes
- [x] 7.6 Add brief staleness detection: compare current brief SHA-256 with stored brief_hash, display warning in status output when different

## 8. Human Checkpoint System

- [x] 8.1 Implement checkpoint trigger logic: count changes completed since last checkpoint, trigger when count >= checkpoint_every, always trigger on failure/stall, always trigger on plan completion, trigger when cumulative tokens exceed token_budget directive
- [x] 8.2 Implement summary generation: write `orchestration-summary.md` with timestamp, per-change table (name/status/progress/tokens/tests), merge queue, total tokens
- [x] 8.3 Implement desktop notifications: `notify-send "wt-orchestrate" "<one-line summary>"` on checkpoint, `notify-send -u critical` on failure — skip when notification directive is "none"
- [x] 8.4 Implement approval gate: set orchestration status to "checkpoint", poll state file every 5 seconds for approval signal, display waiting message
- [x] 8.5 Implement `wt-orchestrate approve` subcommand: write approved=true to latest checkpoint entry, resume orchestration loop
- [x] 8.6 Implement `wt-orchestrate approve --merge`: approve + execute all queued merges before resuming

## 9. Ralph Loop Modifications

- [ ] 9.1 Verify Ralph already writes PID to `.claude/ralph-terminal.pid` (line 590 in wt-loop) — confirm orchestrator can read it for SIGTERM
- [ ] 9.2 Verify Ralph already handles SIGTERM gracefully via cleanup_on_exit trap (line 557-583) — confirm status is set to "stopped" and iteration is recorded
- [ ] 9.3 Verify Ralph restart in existing worktree works: `wt-loop start` with existing tasks.md preserves checked tasks, detect_next_change_action picks up remaining work
- [ ] 9.4 Add integration test: start Ralph, send SIGTERM, verify loop-state.json has status "stopped", restart, verify it continues from correct position

## 10. Testing

- [x] 10.1 Implement `wt-orchestrate self-test` subcommand: run Level 1 unit tests internally — parse_brief with sample input, parse_directives defaults/validation, topological_sort with known graph, state JSON roundtrip, circular dependency detection
- [ ] 10.2 Create test fixture: `tests/orchestrator/sample-brief.md` with 3 dummy features (A independent, B depends on A, C independent) and all directives set
- [ ] 10.3 Level 2 integration test script: `tests/orchestrator/test-plan.sh` — create temp project dir, copy sample brief, run `wt-orchestrate plan`, validate orchestration-plan.json structure (change names kebab-case, deps valid, no circular deps)
- [ ] 10.4 Level 3 end-to-end test script: `tests/orchestrator/test-e2e.sh` — create temp git repo with trivial brief ("add hello.txt"), run `wt-orchestrate plan` + `start`, wait for completion, verify change went through full lifecycle (pending→dispatched→running→done→merged), verify hello.txt exists on main
- [ ] 10.5 Document parallel execution safety model in tests/orchestrator/README.md: worktree isolation, sequential merges, dependency ordering, conflict detection, and how to run each test level

## 11. GUI Orchestrator View (Phase 2)

- [ ] 11.1 Add orchestrator status indicator to project row in wt-control: detect `orchestration-state.json` existence, show "O" badge with status color (green=running, yellow=checkpoint, red=failed)
- [ ] 11.2 Add orchestrator detail panel: read orchestration-state.json, display per-change progress cards with status, iteration count, token usage
- [ ] 11.3 Add dependency graph visualization: render change DAG with status colors using QPainter (similar to DualStripeBar widget pattern)
- [ ] 11.4 Add approve button: when orchestrator is in "checkpoint" status, show approve button that writes approval signal to state file
- [ ] 11.5 Add GUI test for orchestrator panel: test with mock orchestration-state.json, verify status display and approve button interaction
