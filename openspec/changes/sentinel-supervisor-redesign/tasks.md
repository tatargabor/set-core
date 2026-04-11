# Tasks

## 1. Python daemon scaffolding

- [ ] 1.1 Create `lib/set_orch/supervisor/__init__.py` package
- [ ] 1.2 Create `lib/set_orch/supervisor/daemon.py` with the main loop
- [ ] 1.3 Create `lib/set_orch/supervisor/anomaly.py` with the trigger signal detection
- [ ] 1.4 Create `lib/set_orch/supervisor/ephemeral.py` with the Claude subprocess invocation helper
- [ ] 1.5 Create `lib/set_orch/supervisor/canary.py` with the periodic canary check
- [ ] 1.6 Create `bin/set-supervisor` CLI entry point
- [ ] 1.7 Add `lib/set_orch/supervisor/state.py` for supervisor.status.json read/write

## 2. Directive + manager API integration

- [ ] 2.1 Add `supervisor_mode: str = "python"` to Directives
- [ ] 2.2 Parse directive in `parse_directives`
- [ ] 2.3 Update `/api/<project>/sentinel/start` to dispatch based on directive
- [ ] 2.4 Document the directive in the nextjs template config

## 3. Anomaly signal detection

- [ ] 3.1 `process_crash` — `kill -0` fails and status != "done"
- [ ] 3.2 `state_stall` — state.mtime unchanged > 5 min, status == running
- [ ] 3.3 `token_stall` — change tokens > 500k, no commit in 30 min
- [ ] 3.4 `integration_failed` — change.status transitions to integration-failed
- [ ] 3.5 `non_periodic_checkpoint` — checkpoint event with reason != periodic
- [ ] 3.6 `unknown_event_type` — new event type in events.jsonl (first occurrence only)
- [ ] 3.7 `error_rate_spike` — WARN/ERROR rate > 3x rolling baseline
- [ ] 3.8 `log_silence` — no new log lines in 5 min, process alive
- [ ] 3.9 `terminal_state` — final state detected, spawn final report Claude and exit

## 4. Ephemeral Claude invocation

- [ ] 4.1 Implement `spawn_ephemeral_claude(trigger_name, context, timeout=600, model="sonnet")`
- [ ] 4.2 Build trigger-specific prompts for each signal type
- [ ] 4.3 Capture exit code and stdout tail in the SUPERVISOR_TRIGGER event
- [ ] 4.4 Log full ephemeral output to `set/supervisor/claude-<trigger>-<ts>.log`

## 5. Canary check

- [ ] 5.1 Build structured diff generator (merged/running/pending changes, event summary, log anomalies, gate ms moving averages)
- [ ] 5.2 Build canary prompt template with the diff + "anything off?" question
- [ ] 5.3 Parse `CANARY_VERDICT: ok|note|warn|stop` sentinel
- [ ] 5.4 Handle each verdict: ok → log, note → log, warn → escalate with rate limit, stop → halt orchestrator
- [ ] 5.5 Rate-limit repeat warnings about the same pattern (30 min window)

## 6. Observability

- [ ] 6.1 Emit `SUPERVISOR_START` / `SUPERVISOR_STOP` events
- [ ] 6.2 Emit `SUPERVISOR_TRIGGER` event per ephemeral spawn
- [ ] 6.3 Emit `CANARY_CHECK` event per canary run with verdict
- [ ] 6.4 (Optional, follow-up) add a Supervisor panel to the set-web dashboard

## 7. Backwards compatibility

- [ ] 7.1 Test fallback path: `supervisor_mode: claude` starts the legacy sentinel
- [ ] 7.2 Test off path: `supervisor_mode: off` runs the orchestrator without supervision
- [ ] 7.3 Ensure existing sentinel CLI helpers (`set-sentinel-status`, `set-sentinel-finding`, `set-sentinel-inbox`) still work when called from ephemeral Claudes

## 8. Tests

- [ ] 8.1 `tests/unit/test_supervisor_daemon.py` — main loop starts orchestrator, polls, exits cleanly on SIGTERM
- [ ] 8.2 `tests/unit/test_supervisor_anomaly.py` — each trigger signal fires on the right input
- [ ] 8.3 `tests/unit/test_supervisor_ephemeral.py` — mock `claude -p`, verify prompt building and event emission
- [ ] 8.4 `tests/unit/test_supervisor_canary.py` — diff building, verdict parsing, rate limiting
- [ ] 8.5 `tests/unit/test_supervisor_rollback.py` — directive-controlled dispatch between python/claude/off modes

## 9. Documentation

- [ ] 9.1 Update `docs/` with a supervisor architecture overview
- [ ] 9.2 Update `.claude/rules/sentinel-autonomy.md` or rename to `supervisor-autonomy.md`
- [ ] 9.3 Document the anomaly trigger list and how to add new triggers
- [ ] 9.4 Post-migration: delete or reduce `.claude/commands/set/sentinel.md` to a thin wrapper

## 10. Migration + rollout

- [ ] 10.1 Ship the change behind `supervisor_mode: python` default
- [ ] 10.2 Run at least one real orchestration (micro or minishop) with the new supervisor to validate end-to-end
- [ ] 10.3 If validation succeeds, remove the legacy sentinel.md from the consumer template
- [ ] 10.4 Update set-project init to deploy `set/supervisor/` config directory
