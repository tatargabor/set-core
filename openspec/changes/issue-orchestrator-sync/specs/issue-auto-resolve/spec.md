## issue-auto-resolve

### Requirements

- REQ-1: IssueManager.tick() checks orchestration-state.json for affected_change status
- REQ-2: If affected_change has status "merged" in orchestration state, auto-resolve the issue
- REQ-3: Auto-resolve sets resolved_at, transitions to RESOLVED, marks source finding "fixed"
- REQ-4: Issues without affected_change are not auto-resolved (need full fix pipeline)

### Scenarios

**affected-change-merged**
GIVEN ISS-001 has affected_change="auth-navigation" and state="diagnosed"
AND orchestration-state.json shows auth-navigation status="merged"
WHEN IssueManager.tick() runs
THEN ISS-001 transitions to RESOLVED with resolved_at set

**affected-change-still-running**
GIVEN ISS-001 has affected_change="cart-system" and state="investigating"
AND orchestration-state.json shows cart-system status="running"
WHEN IssueManager.tick() runs
THEN ISS-001 stays in "investigating" (no change)

**no-affected-change**
GIVEN ISS-002 has affected_change=None
WHEN IssueManager.tick() runs
THEN ISS-002 is NOT auto-resolved
