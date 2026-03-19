# Tasks: Orchestrator Resume Mode

## Group 1: Auto-resume in cmd_start

- [x] 1. In `dispatcher.sh` `cmd_start()`, add auto-resume detection BEFORE `need_plan` check: if state file has active changes, skip to monitor directly [REQ: REQ-ORM-01]
- [x] 2. Add `_detect_zombies()` helper — checks running changes for dead PIDs, logs warnings [REQ: REQ-ORM-02]
- [x] 3. On resume path, read directives from `wt/orchestration/directives.json`, error if missing [REQ: REQ-ORM-05]
- [x] 4. On resume path, call `dispatch_ready_changes` for pending changes with no worktree, then exec to Python monitor [REQ: REQ-ORM-01]

## Group 2: Resume subcommand

- [x] 5. Add `resume` case in `set-orchestrate` main dispatch — calls `cmd_start` with `FORCE_REPLAN=false` [REQ: REQ-ORM-04]
- [x] 6. In `cmd_start`, respect `FORCE_REPLAN` — if explicitly false, skip `need_plan` check entirely [REQ: REQ-ORM-04]

## Group 3: Sentinel state protection

- [x] 7. In `set-sentinel` "fresh start" logic, replace `rm -f STATE_FILENAME` with `cp STATE_FILENAME STATE_FILENAME.bak` [REQ: REQ-ORM-03]
- [x] 8. In sentinel, don't delete events file — only rotate/backup [REQ: REQ-ORM-03]

## Group 4: Validation

- [x] 9. Test: `set-orchestrate start` with active state → no "Creating plan" in output, monitor starts in <5s
- [x] 10. Test: `set-orchestrate resume` with no state file → error message
- [x] 11. Test: sentinel on done → state.json.bak exists

## Bonus: Post-merge build gate (from E2E findings)

- [x] 12. In `merger.py`, set `build_broken_on_main` flag in state when post-merge build fails
- [x] 13. In `engine.py`, `_dispatch_ready_safe` skips dispatch when `build_broken_on_main` is true
- [x] 14. Clear `build_broken_on_main` flag on next successful post-merge build
