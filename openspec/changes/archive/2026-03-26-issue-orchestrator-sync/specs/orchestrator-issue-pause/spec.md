## orchestrator-issue-pause

### Requirements

- REQ-1: Add `_get_issue_owned_changes(project_path)` that returns change names with active issues (investigating/fixing/awaiting_approval)
- REQ-2: `resume_stalled_changes` must skip changes owned by the issue pipeline
- REQ-3: `retry_merge_queue` (via `execute_merge_queue`) must skip changes owned by the issue pipeline
- REQ-4: Log when a change is skipped due to issue ownership

### Scenarios

**stalled-change-owned-by-issue**
GIVEN auth-navigation is stalled
AND ISS-001 has affected_change="auth-navigation" and state="fixing"
WHEN resume_stalled_changes runs
THEN auth-navigation is NOT redispatched
AND log says "skipping auth-navigation — owned by issue ISS-001"

**stalled-change-no-issue**
GIVEN cart-system is stalled
AND no active issue has affected_change="cart-system"
WHEN resume_stalled_changes runs
THEN cart-system IS redispatched normally
