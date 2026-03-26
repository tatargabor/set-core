## 1. State Machine Fix

- [x] 1.1 Add `IssueState.RESOLVED` to FIXING transitions in `lib/set_orch/issues/models.py` [REQ: auto-fix-state-machine/REQ-1]
- [x] 1.2 Add `IssueState.RESOLVED` to VERIFYING transitions in `lib/set_orch/issues/models.py` [REQ: auto-fix-state-machine/REQ-2]
- [x] 1.3 Verify manager.py FIXING handler transitions to RESOLVED directly [REQ: auto-fix-state-machine/REQ-3]

## 2. Fixer Resilience

- [x] 2.1 Add `_is_pid_alive()` helper to `lib/set_orch/issues/fixer.py` [REQ: auto-fix-state-machine/REQ-5]
- [x] 2.2 Update `fixer.is_done()` to check PID liveness when process reference is lost [REQ: auto-fix-state-machine/REQ-5]
- [x] 2.3 Update `fixer.collect()` to check filesystem (archived change) when process reference is lost [REQ: auto-fix-state-machine/REQ-4]

## 3. Investigator Resilience

- [x] 3.1 Update `investigator.is_done()` to check PID liveness when process reference is lost [REQ: auto-fix-state-machine/REQ-6]
- [x] 3.2 Update `investigator.collect()` to check proposal.md on disk when process reference is lost [REQ: auto-fix-state-machine/REQ-7]

## 4. Finding-Pipeline Sync

- [x] 4.1 Add `_mark_finding_status()` method to DetectionBridge in `lib/set_orch/issues/detector.py` [REQ: finding-issue-sync/REQ-1]
- [x] 4.2 Call `_mark_finding_status("pipeline")` after successful issue registration [REQ: finding-issue-sync/REQ-1]
- [x] 4.3 Add `_save_processed()` and `_load_processed()` to persist `_processed_findings` to disk [REQ: finding-issue-sync/REQ-2]
- [x] 4.4 Load processed findings on DetectionBridge init [REQ: finding-issue-sync/REQ-2]
- [x] 4.5 Add `mark_finding_resolved()` method callable from manager on issue resolution [REQ: finding-issue-sync/REQ-3]

## 5. Sentinel Awareness

- [x] 5.1 Update `.claude/commands/set/sentinel.md` to check finding status before Tier 3 fixes [REQ: finding-issue-sync/REQ-4]

## 6. Manager Integration

- [x] 6.1 Call detector.mark_finding_resolved() when issue transitions to RESOLVED in manager.py [REQ: finding-issue-sync/REQ-3]
