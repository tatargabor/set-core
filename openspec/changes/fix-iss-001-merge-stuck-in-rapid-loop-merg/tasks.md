## 1. Fix recovery logic in engine.py

- [x] 1.1 In `_recover_merge_blocked_safe()`, reset `ff_retry_count` to 0 when recovering merge-blocked → done [REQ: recovery-resets-ff-retry-state]
- [x] 1.2 In `_recover_merge_blocked_safe()`, increment `merge_retry_count` by 1 when recovering [REQ: recovery-increments-merge-retry-counter]
- [x] 1.3 Add INFO log message for the recovery state reset (change name, old ff_retry_count, new merge_retry_count) [REQ: recovery-resets-ff-retry-state]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `_recover_merge_blocked_safe` transitions a change from merge-blocked to done THEN it sets ff_retry_count to 0 and logs the reset [REQ: recovery-resets-ff-retry-state, scenario: recovery-resets-ff-retry-count]
- [x] AC-2: WHEN `_recover_merge_blocked_safe` transitions a change from merge-blocked to done THEN it increments merge_retry_count by 1 [REQ: recovery-increments-merge-retry-counter, scenario: recovery-increments-merge-retry-count]
- [x] AC-3: WHEN a change has been recovered 3 times AND monitor finds it as orphaned done with merge_retry_count >= 3 THEN it transitions to integration-failed [REQ: recovery-increments-merge-retry-counter, scenario: loop-terminates-after-bounded-recoveries]
