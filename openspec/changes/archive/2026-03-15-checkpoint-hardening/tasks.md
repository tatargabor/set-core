## 1. Directive and State Infrastructure

- [x] 1.1 Add `checkpoint_timeout: int = 0` field to `Directives` dataclass in `lib/wt_orch/engine.py`
- [x] 1.2 Add `checkpoint_timeout` parsing in `parse_directives()` using `_int(raw, "checkpoint_timeout", d.checkpoint_timeout)`
- [x] 1.3 Add `--checkpoint-timeout` CLI argument to the monitor subparser in `lib/wt_orch/cli.py` and forward it to `Directives`

## 2. Checkpoint Trigger Hardening

- [x] 2.1 Modify `trigger_checkpoint()` in `lib/wt_orch/engine.py` to reset `changes_since_checkpoint` to `0` after setting checkpoint status
- [x] 2.2 Modify `trigger_checkpoint()` to store `checkpoint_started_at` (epoch seconds) in state extras for timeout tracking
- [x] 2.3 Modify `trigger_checkpoint()` to append a checkpoint record to `state.checkpoints` with `reason`, `triggered_at`, `changes_completed`, and `approved: false`

## 3. Monitor Loop Approval Integration

- [x] 3.1 Add `_checkpoint_approved(state)` helper function in `lib/wt_orch/engine.py` that checks `state.checkpoints[-1].get("approved", False)` (handling both dataclass field and extras fallback)
- [x] 3.2 Update the checkpoint block in `monitor_loop()` to check `_checkpoint_approved(state)` when `checkpoint_auto_approve` is `false`, resuming to "running" if approved

## 4. Checkpoint Timeout

- [x] 4.1 Add timeout check in the checkpoint block of `monitor_loop()`: compare `checkpoint_started_at` against current time, auto-resume with warning if `checkpoint_timeout` exceeded
- [x] 4.2 Emit `CHECKPOINT_TIMEOUT` event with elapsed duration when timeout triggers auto-resume

## 5. Restart State Cleanup

- [x] 5.1 In the resume/restart path in `monitor_loop()`, clear `checkpoint_reason` from state extras
- [x] 5.2 In the resume/restart path, clear `checkpoint_started_at` from state extras
- [x] 5.3 In the resume/restart path, reset `changes_since_checkpoint` to `0`
- [x] 5.4 In the resume/restart path, if status is "checkpoint", change it to "running" with a log entry noting stale checkpoint cleared

## 6. Unit Tests

- [x] 6.1 Add test for `checkpoint_timeout` directive parsing (present and absent) in `tests/unit/test_engine.py`
- [x] 6.2 Add test for `trigger_checkpoint()` resetting `changes_since_checkpoint` to `0`
- [x] 6.3 Add test for `trigger_checkpoint()` storing `checkpoint_started_at` in state extras
- [x] 6.4 Add test for `trigger_checkpoint()` appending checkpoint record to `state.checkpoints`
- [x] 6.5 Add test for `_checkpoint_approved()` returning `true` when latest checkpoint has `approved: true`
- [x] 6.6 Add test for `_checkpoint_approved()` returning `false` when no checkpoints exist
- [x] 6.7 Add test for checkpoint timeout auto-resume logic (mock time to exceed timeout)
- [x] 6.8 Add test for checkpoint counter reset cadence: with `checkpoint_every=3`, verify checkpoint triggers at 3, 6, 9 changes (not 3, 6, 9 cumulative)
