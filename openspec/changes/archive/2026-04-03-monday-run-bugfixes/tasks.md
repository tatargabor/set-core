## 1. Test Gate No-Test-Files Detection

- [x] 1.1 In `merger.py` `_run_integration_gates()`, EXTEND the existing `missing_indicators` list (line ~836) with no-test-files patterns: `"No test suite found"`, `"no test files found"`, `"No tests found, exiting with code 1"` [REQ: test-gate-detects-no-test-files-and-skips]
- [x] 1.2 Ensure the skip path logs: "Integration gate: test skipped for {change} (no test files found)" [REQ: test-gate-detects-no-test-files-and-skips]

## 2. Same-Output Retry Detection

- [x] 2.1 After a gate fails in `_run_integration_gates()`, compute SHA256 hash of first 2000 chars of gate output [REQ: gate-retry-stops-when-output-is-identical]
- [x] 2.2 Store the hash in `change.extras["gate_output_hashes"]` (persisted list via `update_change_field`) — append on fail, reset on different hash [REQ: gate-retry-stops-when-output-is-identical]
- [x] 2.3 In `retry_merge_queue()`, before re-queuing, check if `gate_output_hashes` has 3+ identical consecutive entries — if so, mark `integration-failed` with `integration_gate_fail="{gate}_identical_output"` [REQ: gate-retry-stops-when-output-is-identical]

## 3. total_merge_attempts TypeError Fix

- [x] 3.1 In `merger.py:632`, replace `change.extras.get("total_merge_attempts", 0)` with `int(change.extras.get("total_merge_attempts") or 0)` [REQ: total-merge-attempts-is-always-an-integer]
- [x] 3.2 In `merger.py:1110`, apply same int() coercion [REQ: total-merge-attempts-is-always-an-integer]
- [x] 3.3 In `merger.py:1132`, ensure assignment always writes int, not None [REQ: total-merge-attempts-is-always-an-integer]
- [x] 3.4 Search for any other `total_merge_attempts` usage and apply same pattern [REQ: total-merge-attempts-is-always-an-integer]

## 4. Pre-Merge Dependency Validation

- [x] 4.1 In `execute_merge_queue()`, before running integration gates for a change, validate all `depends_on` entries have status in (`merged`, `done`, `skip_merged`, `completed`) [REQ: pre-merge-dependency-validation]
- [x] 4.2 If any dep is not in terminal status, remove change from queue, set status to `dep-blocked`, log: "Pre-merge dep check: {change} blocked — waiting for {dep1}, {dep2}" [REQ: pre-merge-dependency-validation]
- [x] 4.3 In engine.py (`_retry_merge_queue_safe` or poll loop), add check: if status is `dep-blocked` and all deps now in terminal status → set back to `done` for re-queue [REQ: pre-merge-dependency-validation]

## 5. Merge-Blocked Auto-Recovery

- [x] 5.1 In engine.py poll loop, scan for `merge-blocked` changes [REQ: merge-blocked-auto-recovery-on-issue-resolution]
- [x] 5.2 For each merge-blocked change, query issue registry for issues where `issue.change == change_name` [REQ: merge-blocked-auto-recovery-on-issue-resolution]
- [x] 5.3 If all matching issues have state `resolved`/`closed`/`dismissed`, OR no issues found → set status to `done` to re-enter merge queue [REQ: merge-blocked-auto-recovery-on-issue-resolution]
- [x] 5.4 If any matching issue has state `open`/`investigating`/`diagnosed` → keep `merge-blocked`, no action [REQ: merge-blocked-auto-recovery-on-issue-resolution]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN vitest output contains "no test files found" AND exit code non-zero THEN gate result is `skip` [REQ: test-gate-detects-no-test-files-and-skips, scenario: vitest-exits-with-no-test-files-found]
- [x] AC-2: WHEN vitest has actual test failures THEN gate result is `fail` as before [REQ: test-gate-detects-no-test-files-and-skips, scenario: vitest-exits-with-actual-test-failure]
- [x] AC-3: WHEN 3 consecutive retries have identical output hash THEN gate stops retrying [REQ: gate-retry-stops-when-output-is-identical, scenario: same-output-on-3-consecutive-retries]
- [x] AC-4: WHEN extras contains None for total_merge_attempts THEN coerced to 0, no TypeError [REQ: total-merge-attempts-is-always-an-integer, scenario: extras-field-contains-none-value]
- [x] AC-5: WHEN change has unmerged dependency THEN removed from merge queue and set to dep-blocked [REQ: pre-merge-dependency-validation, scenario: dependency-not-yet-on-main]
- [x] AC-6: WHEN dep-blocked change's deps all merge THEN status returns to done [REQ: pre-merge-dependency-validation, scenario: dependency-merges-later-triggers-re-queue]
- [x] AC-7: WHEN merge-blocked change has no active blocking issues THEN status returns to done [REQ: merge-blocked-auto-recovery-on-issue-resolution, scenario: blocking-issue-resolved]
