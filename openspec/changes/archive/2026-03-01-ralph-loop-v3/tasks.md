# Tasks

## FF Exhausted Recovery

- [x] 1.1 Add `generate_fallback_tasks()` function to wt-loop — reads proposal.md (and design.md if present) from the change directory, writes a single-task tasks.md: `# Tasks\n\n- [ ] Implement the change as described in proposal.md and design.md`
- [x] 1.2 Modify ff_exhausted handler (~line 1199) — instead of stalling, check if tasks.md exists; if not and proposal.md exists, call `generate_fallback_tasks()`, reset `ff_attempts` to 0, log warning, set `iter_ff_recovered=true`, and continue loop
- [x] 1.3 Add `ff_recovered` field to iteration record in `add_iteration()` — boolean, default false, set when fallback was generated

## Real-time Terminal Output

- [x] 2.1 Detect `stdbuf` availability at loop start — `STDBUF_CMD=$(command -v stdbuf 2>/dev/null || true)`, log warning if not found
- [x] 2.2 Modify Claude invocation pipe (~lines 934-939) — wrap both `claude` and `tee` with `stdbuf -oL` when available: `$STDBUF_PREFIX claude ... 2>&1 | $STDBUF_PREFIX tee -a "$iter_log_file"`
- [x] 2.3 Test line-buffered output manually — start wt-loop, confirm terminal shows output line-by-line during Claude execution (not buffered until end)
