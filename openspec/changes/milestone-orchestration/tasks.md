## 1. Plan JSON Schema — Phase Field

- [x] 1.1 Add `"phase": 1` field to `_SPEC_OUTPUT_JSON`, `_SPEC_OUTPUT_JSON_DIGEST`, and `_BRIEF_OUTPUT_JSON` in `lib/wt_orch/templates.py`. Add it after the `depends_on` field in each schema.
- [x] 1.2 Add phase assignment instruction to the decompose prompt in `render_planning_prompt()`: "Assign a phase integer (1..N, max 5) to each change. Phase 1: infrastructure/schema/foundational. Phases 2..N-1: features grouped by domain coherence. Last phase: cleanup-after/polish. For specs with fewer than 4 changes, assign all to phase 1."
- [x] 1.3 Update `wt-orch-core state init` (the Python command that reads plan JSON and creates state) to propagate the `phase` field from plan changes to state changes. Default to phase 1 if missing.

## 2. Phase State Tracking

- [x] 2.1 Add phase state initialization to `init_state()` in `lib/orchestration/state.sh` — after `wt-orch-core state init`, compute unique phases from changes and create the `phases` object (`{status: "pending", tag: null, server_port: null, server_pid: null, completed_at: null}` per phase). Set `current_phase: 1`.
- [x] 2.2 Add `milestones` config parsing in `monitor_loop()` in `lib/orchestration/monitor.sh` — read `milestones.enabled`, `milestones.dev_server`, `milestones.base_port` (default 3100), `milestones.max_worktrees` (default 3), `milestones.phase_overrides` from directives.
- [x] 2.3 Apply phase overrides: after state init, if `milestones.phase_overrides` exists in directives, update matching changes' `phase` field and recalculate the `phases` object.

## 3. Phase-Gated Dispatch

- [x] 3.1 Modify `dispatch_ready_changes()` in `lib/orchestration/dispatcher.sh` — add phase filter: when milestones enabled, skip changes where `phase > current_phase`. Add after the `status != "pending"` check. Read `current_phase` from state, default to 999 (no gating) if milestones disabled.
- [x] 3.2 Add `advance_phase()` function in `lib/orchestration/state.sh` — called when all changes in `current_phase` are terminal. Increments `current_phase`, marks completed phase as `completed` with timestamp, marks next phase as `running`. Returns 0 if advanced, 1 if no more phases.
- [x] 3.3 Add phase completion detection to the monitor loop in `monitor.sh` — after `dispatch_ready_changes()`, check if all changes in `current_phase` are terminal. If so, call `run_milestone_checkpoint()` then `advance_phase()`. Only when milestones enabled. Note: the monitor self-watchdog (MONITOR_IDLE_TIMEOUT, added in gate-reliability) will auto-detect if phase transition stalls.

## 4. Dev Server Auto-Detection

- [x] 4.1 Create `lib/orchestration/server-detect.sh` with `detect_dev_server()` function. Detection order: (1) check `milestones.dev_server` directive, (2) fall back to `smoke_dev_server_command` directive if set (reuse existing smoke config), (3) package.json scripts.dev → npm/bun run dev, (4) docker-compose.yml/compose.yml → docker compose up, (5) Makefile dev/serve target → make dev, (6) manage.py → python manage.py runserver. Returns command string or empty.
- [x] 4.2 Add `detect_package_manager()` helper in same file — checks for bun.lockb (bun), pnpm-lock.yaml (pnpm), yarn.lock (yarn), defaults to npm. Used by both server detection and dependency install.
- [x] 4.3 Add `install_dependencies()` function — runs appropriate install command based on detected package manager. Timeout 120s. Returns 0 on success, 1 on failure (non-blocking).

## 5. Milestone Checkpoint

- [x] 5.1 Create `lib/orchestration/milestone.sh` with `run_milestone_checkpoint()` function. Args: phase_number. Steps: (1) git tag, (2) create worktree, (3) install deps, (4) start server, (5) send email, (6) log + emit event. Source `server-detect.sh`.
- [x] 5.2 Implement git tagging: `git tag -f "milestone/phase-$N" HEAD`. Store tag name in `phases["$N"].tag`.
- [x] 5.3 Implement worktree creation: `git worktree add .claude/milestones/phase-$N milestone/phase-$N`. Before creating, check max_worktrees limit and remove oldest if exceeded (kill server + git worktree remove).
- [x] 5.4 Implement dev server start: follow the `smoke_dev_server_command` pattern from `merger.sh` (PID tracking, health check wait). Run `install_dependencies` then detected command with `PORT=$((base_port + N))` in background. Store PID and port in state. If `smoke_health_check_url` pattern is configured, use `health_check()` to verify; otherwise wait 5s and check if process is alive. Warn if dead.
- [x] 5.5 Implement milestone email: use `send_email()` with phase summary (changes merged, tokens, server URL). Subject: `[wt-tools] <project> — Phase N complete (M/T changes)`.
- [x] 5.6 Add `MILESTONE_COMPLETE` event type. Emit with phase number, change count, server port, tag name.

## 6. Cleanup

- [x] 6.1 Add `cleanup_milestone_servers()` function in `milestone.sh` — reads all `phases[*].server_pid` from state, kills each with SIGTERM, clears PIDs from state.
- [x] 6.2 Add `cleanup_milestone_worktrees()` function — removes all `.claude/milestones/phase-*` worktrees via `git worktree remove --force`.
- [x] 6.3 Integrate cleanup into `cleanup_all_worktrees()` (called on orchestration completion/stop in monitor.sh) — call both cleanup functions if milestones enabled. Also integrate with the existing `_ORCH_DEV_SERVER_PID` cleanup in dispatcher.sh trap handler to ensure milestone PIDs are also killed on crash.

## 7. HTML Report — Phase View

- [x] 7.1 Add `render_milestone_section()` function in `lib/orchestration/reporter.sh` — reads phase data from state, renders a table with: Phase#, Status (color-coded), Changes (merged/total), Server URL (clickable link), Completed At.
- [x] 7.2 Integrate into `generate_report()` — call `render_milestone_section()` between plan and execution sections. Only render if `phases` exists in state.
- [x] 7.3 Modify `render_execution_section()` — when phases exist, group changes under phase headers. Each header shows "Phase N" with aggregate tokens.

## 8. CLI Status — Phase Display

- [x] 8.1 Add milestone progress display to `cmd_status()` in `state.sh` — after the progress line, show "Milestones: Phase X/Y" and a compact per-phase summary. Include server URLs for completed phases.
- [x] 8.2 Add per-phase token breakdown to the total tokens line — e.g., "Total tokens: 4M (P1: 1.2M, P2: 2M, P3: 0.8M)".

## 9. Integration & Wiring

- [x] 9.1 Source `milestone.sh` and `server-detect.sh` in `bin/wt-orchestrate` (after existing sources).
- [x] 9.2 Add `milestones` section to directive resolution in `lib/orchestration/config.sh` (or wherever `resolve_directives` handles orchestration.yaml) — parse `milestones.enabled`, `milestones.dev_server`, `milestones.base_port`, `milestones.max_worktrees`, `milestones.phase_overrides`.
- [x] 9.3 Update `send_summary_email()` in `lib/notify-email.sh` — include per-phase breakdown in completion email when phases exist in state.

## 10. Testing

- [x] 10.1 Unit test for `detect_dev_server()` — mock different project files (package.json, docker-compose, Makefile, manage.py) and verify correct command detection. Test override via directive.
- [x] 10.2 Unit test for `advance_phase()` — verify phase transition logic, terminal state detection, current_phase increment.
- [x] 10.3 Unit test for phase-gated dispatch — create a state with changes in phases 1 and 2, verify only phase 1 dispatched when current_phase=1.
- [x] 10.4 Integration test: full milestone flow — create a plan with 2 phases, mock dispatch/merge, verify git tags created, worktrees exist, phase state transitions correct, cleanup removes worktrees.
