# Spec: Cumulative Review Feedback

## Requirements

### REQ-CRF-01: Review history accumulation
When the verify gate finds a CRITICAL review issue, append a structured entry to `review_history` on the change state. Entry contains: attempt number, timestamp, review output (1500 char), extracted fixes, and diff summary of what the agent changed since last attempt.

### REQ-CRF-02: Squashed retry prompt with prior attempts
The retry prompt MUST include a "PREVIOUS ATTEMPTS" section listing what was tried before and what the outcome was. Each prior attempt shows: extracted fixes and diff summary. The section ends with "Try a fundamentally different strategy."

### REQ-CRF-03: Diff capture between retries
Before appending to review_history, capture `git diff --stat HEAD~1` in the worktree to record what the agent changed in the last retry. Truncate to 500 chars. First attempt has null diff_summary.

### REQ-CRF-04: History-aware prompt escalation
- Attempt 1: standard fix instructions + security reference
- Attempt 2+: add "PREVIOUS ATTEMPTS — DO NOT REPEAT" section
- Final attempt: add "This is your LAST attempt. If the same approach hasn't worked, restructure the entire implementation."

## Scenarios

### WHEN review finds CRITICAL on first attempt
THEN review_history has 1 entry with diff_summary=null
AND retry_context contains fix instructions without "PREVIOUS ATTEMPTS" section

### WHEN review finds CRITICAL on second attempt
THEN review_history has 2 entries
AND retry_context contains "PREVIOUS ATTEMPTS" section with attempt 1 details
AND retry_context contains "Try a fundamentally different strategy"

### WHEN review finds CRITICAL on final attempt (retry_limit reached)
THEN review_history has N entries (complete record)
AND change status set to "failed"
AND review_history preserved in state for wrap-up analysis
