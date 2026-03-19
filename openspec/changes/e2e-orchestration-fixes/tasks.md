## 1. Scaffold branch rename

- [ ] 1.1 In `tests/e2e/run-complex.sh`, add `git branch -m spec-only main` after the `v1-ready` tag line
- [ ] 1.2 In `tests/e2e/run.sh`, add the same branch rename if `spec-only` branch exists
- [ ] 1.3 Verify: run `run-complex.sh`, confirm main branch is `main` not `spec-only`

## 2. build_broken_on_main auto-clear

- [ ] 2.1 In `lib/set_orch/loop.py` (or `engine.py`), find the monitor poll loop and add a build retry check every 5th cycle
- [ ] 2.2 When `build_broken_on_main` is True, run the build command on main worktree
- [ ] 2.3 If build passes, clear the flag and emit a log/event: "Build on main recovered — dispatch resumed"
- [ ] 2.4 If build still fails, log and continue (don't spam retries faster than every 75s)

## 3. Memory project resolution

- [ ] 3.1 In `bin/set-hook-memory-recall`, check `CLAUDE_PROJECT_DIR` env var first for project resolution
- [ ] 3.2 In `bin/set-hook-memory-warmstart`, same fix
- [ ] 3.3 In `bin/set-hook-memory-pretool`, same fix
- [ ] 3.4 In `bin/set-hook-memory-posttool`, same fix
- [ ] 3.5 In `bin/set-hook-memory-save`, same fix
- [ ] 3.6 Verify: set `CLAUDE_PROJECT_DIR=/tmp/test`, run hook, confirm it resolves to `test` project

## 4. Config template

- [ ] 4.1 In `tests/e2e/run-complex.sh`, update the orchestration config to include `# default_model: opus-1m  # for 1M context window` as comment
- [ ] 4.2 In `tests/e2e/run.sh`, same update

## 5. Python monitor heartbeat

- [ ] 5.1 In the Python monitor poll loop (`lib/set_orch/engine.py` or `loop.py`), emit a log line each cycle: `[monitor] heartbeat: N changes tracked, M running`
- [ ] 5.2 In `bin/set-sentinel`, update the watchdog "no progress" check to also look for recent monitor heartbeat lines in the log (not just events.jsonl)
- [ ] 5.3 Verify: start orchestration, confirm sentinel log shows heartbeats and no false "no progress" alarms
