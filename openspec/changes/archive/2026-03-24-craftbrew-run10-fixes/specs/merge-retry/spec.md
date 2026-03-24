# Merge Retry Counter

## Requirements

- MERGE-RETRY-001: `retry_merge_queue()` MUST track `merge_retry_count` in change extras, incrementing on each retry attempt.
- MERGE-RETRY-002: When `merge_retry_count` >= 3, the change MUST be set to `integration-failed` status (terminal) instead of re-adding to queue.
- MERGE-RETRY-003: The retry counter MUST be reset when the change is redispatched to an agent for fixes (so agent fixes get fresh retry budget).
