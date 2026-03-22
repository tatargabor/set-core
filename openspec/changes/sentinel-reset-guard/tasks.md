## 1. Hash persistence

- [ ] 1.1 In `bin/set-sentinel`, after computing spec hash, persist it to `sentinel-state.json` in the run directory (`{"spec_hash": "<hash>", "updated_at": "<iso>"}`) [REQ: sentinel-persists-spec-hash]
- [ ] 1.2 On sentinel start, read `sentinel-state.json` for the previous hash instead of defaulting to "unknown" [REQ: sentinel-persists-spec-hash, scenario: sentinel-restart-preserves-hash]

## 2. Reset approval gate

- [ ] 2.1 Before `_reset_orchestration()`, write `.sentinel-reset-pending` file with reason and timestamp [REQ: reset-requires-approval]
- [ ] 2.2 After writing pending file, poll for `.sentinel-approve-reset` file every 10 seconds, timeout 5 minutes [REQ: reset-requires-approval]
- [ ] 2.3 If approval arrives, proceed with reset and clean up both marker files [REQ: reset-requires-approval, scenario: spec-actually-changed-operator-approves]
- [ ] 2.4 If timeout, skip reset, log warning, continue with existing state, clean up pending file [REQ: reset-requires-approval, scenario: no-approval-within-timeout]

## 3. Auto-approve flag

- [ ] 3.1 Add `--auto-approve-reset` flag to sentinel argument parsing [REQ: auto-approve-flag-for-unattended-runs]
- [ ] 3.2 When flag is set, skip approval gate and reset immediately (current behavior) [REQ: auto-approve-flag-for-unattended-runs, scenario: unattended-run-with-auto-approve]

## 4. Tests

- [ ] 4.1 Unit test: sentinel-state.json written after hash computation
- [ ] 4.2 Unit test: hash read from sentinel-state.json on restart (not "unknown")
- [ ] 4.3 Unit test: reset blocked when no approval file, continues after timeout
- [ ] 4.4 Unit test: --auto-approve-reset skips approval gate
- [ ] 4.5 Run existing tests: must all pass
