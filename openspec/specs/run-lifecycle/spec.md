# Spec: Run Lifecycle Cleanup

## Requirements

### REQ-RLC-001: Archive previous run on new startup
When the sentinel starts and finds a terminal state (done/stopped), it must archive the previous run's artifacts to `set/orchestration/runs/<timestamp>/` before cleaning up.

**Acceptance Criteria:**
- [ ] AC1: State file, events, coverage, review findings are copied to timestamped archive dir
- [ ] AC2: `meta.json` is written with spec_hash, status, change counts, timestamps
- [ ] AC3: Archive is skipped if no state file exists (fresh project)
- [ ] AC4: Archive is idempotent — safe to call multiple times

### REQ-RLC-002: Coverage reset on new run
Coverage.json must be reset to empty when starting a new orchestration cycle, preventing stale change→requirement mappings from prior runs appearing in the dashboard.

**Acceptance Criteria:**
- [ ] AC1: Coverage is reset to `{"coverage": {}, "uncovered": []}` after archive
- [ ] AC2: Coverage is NOT reset during replan within the same run
- [ ] AC3: Digest requirement/dependency files are preserved (spec-derived, not run-derived)

### REQ-RLC-003: Unified cleanup path
`reset_for_spec_switch()`, sentinel startup cleanup, and `cmd_reset --full` must share the same archive+cleanup function instead of having independent implementations.

**Acceptance Criteria:**
- [ ] AC1: `archive_previous_run()` function exists in set-sentinel
- [ ] AC2: `reset_for_spec_switch()` calls `archive_previous_run()` before git cleanup
- [ ] AC3: Sentinel startup (done/stopped state) calls `archive_previous_run()`
- [ ] AC4: `cmd_reset --full` in set-orchestrate calls archive before reset
- [ ] AC5: Partial reset (`cmd_reset --partial`) does NOT archive

### REQ-RLC-004: Review findings cleanup
Review findings must not accumulate across runs.

**Acceptance Criteria:**
- [ ] AC1: `review-findings.jsonl` is archived and deleted on new run
- [ ] AC2: `review-findings-summary.md` is archived and deleted on new run

### REQ-RLC-005: Run history browsable
Previous runs are preserved in a structured directory for post-mortem analysis.

**Acceptance Criteria:**
- [ ] AC1: `set/orchestration/runs/` contains one dir per archived run
- [ ] AC2: Each run dir has state.json, events.jsonl, coverage.json, meta.json
- [ ] AC3: Timestamp format is ISO-8601 safe for filenames (colons replaced)
