## auto-fix-state-machine

### Requirements

- REQ-1: VALID_TRANSITIONS must allow FIXING → RESOLVED transition
- REQ-2: VALID_TRANSITIONS must allow VERIFYING → RESOLVED transition (legacy path)
- REQ-3: manager.py FIXING handler must transition directly to RESOLVED on collect success
- REQ-4: fixer.collect() must check filesystem when process reference is lost (archived change = success)
- REQ-5: fixer.is_done() must check PID liveness when process reference is lost
- REQ-6: investigator.is_done() must check PID liveness when process reference is lost
- REQ-7: investigator.collect() must check proposal.md existence when process reference is lost

### Scenarios

**fixing-to-resolved**
GIVEN an issue in FIXING state
WHEN the fix agent completes and collect returns success
THEN the issue transitions directly to RESOLVED with resolved_at set

**process-reference-lost**
GIVEN an issue in FIXING state with fix_agent_pid set
WHEN the service restarts and _processes dict is empty
AND the openspec change has been archived on disk
THEN collect returns success=True based on filesystem check

**investigation-process-lost**
GIVEN an issue in INVESTIGATING state with fix_agent_pid set
WHEN the process reference is lost
AND proposal.md exists in openspec/changes/{change_name}/
THEN collect returns a valid Diagnosis parsed from proposal.md
