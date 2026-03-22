## 1. Hash persistence

- [x] 1.1 In `bin/set-sentinel`, after computing spec hash, persist it to `sentinel-state.json` in the sentinel dir [REQ: sentinel-persists-spec-hash]
- [x] 1.2 On sentinel start, read `sentinel-state.json` for the previous hash instead of defaulting to "unknown" [REQ: sentinel-persists-spec-hash, scenario: sentinel-restart-preserves-hash]

## 2. Reset approval gate

- [x] 2.1 Before `reset_for_spec_switch()`, call `wait_for_reset_approval()` which writes `.sentinel-reset-pending` and waits [REQ: reset-requires-approval]
- [x] 2.2 Poll for `.sentinel-approve-reset` file every 10 seconds, timeout 5 minutes [REQ: reset-requires-approval]
- [x] 2.3 If approval arrives, proceed with reset and clean up both marker files [REQ: reset-requires-approval, scenario: spec-actually-changed-operator-approves]
- [x] 2.4 If timeout, skip reset, log warning, continue with existing state [REQ: reset-requires-approval, scenario: no-approval-within-timeout]

## 3. Auto-approve flag

- [x] 3.1 Add `--auto-approve-reset` flag to sentinel argument parsing [REQ: auto-approve-flag-for-unattended-runs]
- [x] 3.2 When flag is set, skip approval gate and reset immediately [REQ: auto-approve-flag-for-unattended-runs, scenario: unattended-run-with-auto-approve]

## 4. Tests

- [x] 4.1 Manual test: sentinel restart without spec change → no reset triggered
- [x] 4.2 Manual test: --auto-approve-reset skips approval gate
- [ ] 4.3 Unit tests deferred — bash script testing infrastructure not available
