# Tasks: Remove CLI set-sentinel

## 1. Remove CLI scripts

- [x] 1.1 Delete `bin/set-sentinel` (1135 lines) [REQ: cli-bash-supervisor]
- [x] 1.2 Delete `bin/set-sentinel-rotate` (only called by set-sentinel) [REQ: cli-log-rotation]

## 2. Fix Python code that calls set-sentinel binary

- [x] 2.1 Update `lib/set_orch/api/actions.py` `start_orchestration()` — replace `set-sentinel` binary spawn with `set-orchestrate start` [REQ: cli-bash-supervisor]
- [x] 2.2 Update `lib/set_orch/_api_old.py` same pattern (if still used) [REQ: cli-bash-supervisor]

## 3. Update documentation (non-archive)

- [x] 3.1 Update `README.md` — remove `set-sentinel` CLI references [REQ: cli-bash-supervisor]
- [x] 3.2 Update `install.sh` — remove `set-sentinel` from PATH/install instructions [REQ: cli-bash-supervisor]
- [x] 3.3 Update `docs/orchestration.md` — replace CLI sentinel references with skill or `set-orchestrate start` [REQ: cli-bash-supervisor]
- [x] 3.4 Update `docs/howitworks/en/06b-sentinel.md` [REQ: cli-bash-supervisor]
- [x] 3.5 Update `docs/howitworks/hu/06b-sentinel.md` [REQ: cli-bash-supervisor]
- [x] 3.6 Update `docs/howitworks/en/00d-development.md` and `00e-ecosystem.md` [REQ: cli-bash-supervisor]
- [x] 3.7 Update `docs/howitworks/hu/00d-fejlodes.md` and `00e-okoszisztema.md` [REQ: cli-bash-supervisor]
- [x] 3.8 Update `.claude/rules/capability-guide.md` — remove `set-sentinel` from CLI tools table [REQ: cli-bash-supervisor]
- [x] 3.9 Update `.claude/skills/set/SKILL.md` — remove CLI sentinel references [REQ: cli-bash-supervisor]
- [x] 3.10 Update `scripts/migrate-to-set.sh` [REQ: cli-bash-supervisor]

## 4. Update E2E test infrastructure

- [x] 4.1 Update `tests/e2e/runners/run-minishop.sh` — use `set-orchestrate start` or web UI [REQ: cli-bash-supervisor]
- [x] 4.2 Update `tests/e2e/runners/run-craftbrew.sh` [REQ: cli-bash-supervisor]
- [x] 4.3 Update `tests/e2e/runners/run-micro-web.sh` [REQ: cli-bash-supervisor]
- [x] 4.4 Update `tests/e2e/runners/run-micro-blog.sh` [REQ: cli-bash-supervisor]
- [x] 4.5 Update `tests/e2e/README.md` [REQ: cli-bash-supervisor]
- [x] 4.6 Review `tests/graceful-shutdown/test_graceful_shutdown.sh` — removed (tested bash sentinel only) [REQ: cli-bash-supervisor]
- [x] 4.7 Review `tests/orchestrator/test-sentinel-v2.sh` — removed (tested bash sentinel only) [REQ: cli-bash-supervisor]

## 5. Verify nothing breaks

- [x] 5.1 Grep for remaining `set-sentinel` references — updated cli-reference.md, sentinel.md; remaining refs are helper scripts, specs, skill, historical logs [REQ: cli-bash-supervisor]
- [x] 5.2 Verify web UI Start Sentinel still works — supervisor.py path unchanged, uses Claude skill not bash [REQ: cli-bash-supervisor]
- [x] 5.3 Verify `set-orchestrate start` works standalone — actions.py now spawns set-orchestrate directly [REQ: cli-bash-supervisor]
