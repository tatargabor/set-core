# Merge Retry Counter Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Merge retry limit enforcement

The merge retry counter SHALL be checked in ALL code paths that attempt merging, not just `retry_merge_queue()`. Specifically, `execute_merge_queue()` MUST check `merge_retry_count` before calling `merge_change()` and skip changes that have exceeded the limit (MAX_MERGE_RETRIES=3).

The monitor's "orphaned done" logic in `_poll_suspended_changes()` MUST also check the retry counter before re-adding a change to the merge queue.

**Additionally**, the recovery path (`_recover_merge_blocked_safe`) MUST increment `merge_retry_count` when recovering a merge-blocked change, so that recovery attempts count toward the global retry budget.

#### Scenario: Change exceeds retry limit in execute_merge_queue
- **WHEN** `execute_merge_queue()` processes a change with `merge_retry_count >= 3`
- **THEN** it sets the change status to `integration-failed`, removes it from the merge queue, and does NOT call `merge_change()`

#### Scenario: Monitor does not re-add exhausted changes
- **WHEN** `_poll_suspended_changes()` finds an orphaned "done" change with `merge_retry_count >= 3`
- **THEN** it sets the change status to `integration-failed` instead of re-adding to the merge queue

#### Scenario: Retry counter increments only in retry_merge_queue
- **WHEN** `retry_merge_queue()` re-adds a merge-blocked change to the queue
- **THEN** `merge_retry_count` in change extras is incremented by 1 (single increment point to avoid double-counting)

#### Scenario: Recovery path increments merge_retry_count
- **WHEN** `_recover_merge_blocked_safe` recovers a merge-blocked change to done
- **THEN** `merge_retry_count` in change extras is incremented by 1

#### Scenario: Integration-failed event is emitted
- **WHEN** a change reaches `integration-failed` status due to retry limit
- **THEN** a `CHANGE_INTEGRATION_FAILED` event is emitted with the change name and retry count
