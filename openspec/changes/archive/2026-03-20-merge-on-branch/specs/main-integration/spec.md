# Spec: main-integration

## ADDED Requirements

## IN SCOPE
- Merging main into the feature branch before gate checks run
- Conflict detection and resolution on the feature branch (not main)
- Setting change status to "integrating" during the integration phase
- Aborting integration and marking change as "integration-failed" on unresolvable conflicts
- Agent-assisted conflict resolution on the branch worktree

## OUT OF SCOPE
- Changes to the gate pipeline itself (build, test, review gates remain unchanged)
- Changes to how agents implement features (dispatch, loop, done criteria)
- Conflict resolution strategies for specific file types (existing set-merge logic handles this)
- Remote origin operations (integration uses local branch refs only)

### Requirement: Integrate main before gates
The verifier SHALL merge the main branch into the feature branch before running the gate pipeline. This integration step SHALL occur after the agent signals completion (loop-state done) and before any gate (build, test, review, etc.) executes. The integration SHALL use the local main branch ref, not a remote fetch.

#### Scenario: Successful integration with no conflicts
- **WHEN** a change signals done and main has diverged from the branch's fork point
- **THEN** the system merges main into the branch, sets status to "integrating" during the merge, and proceeds to run gates on the integrated branch

#### Scenario: Integration with no new commits on main
- **WHEN** a change signals done and main has not advanced since the branch was created
- **THEN** the system skips the integration merge (branch is already up-to-date) and proceeds directly to gates

#### Scenario: Integration merge conflict
- **WHEN** the merge of main into the branch produces conflicts
- **THEN** the system dispatches the agent to resolve conflicts on the branch (worktree still alive, context preserved), with a retry prompt explaining the conflict

#### Scenario: Conflict resolution succeeds
- **WHEN** the agent resolves integration conflicts and signals done again
- **THEN** the system re-attempts integration (main may have advanced further) and proceeds to gates once integration succeeds cleanly

#### Scenario: Conflict resolution exhausts retries
- **WHEN** integration conflict resolution fails after the maximum retry count
- **THEN** the system marks the change as "integration-failed" and stops retrying

### Requirement: Integration status tracking
The orchestrator state SHALL include an "integrating" status value for changes undergoing main integration. The status transition SHALL be: running -> integrating -> verifying (or integration-failed).

#### Scenario: Status visible during integration
- **WHEN** a change is being integrated with main
- **THEN** the change status in orchestrator state reads "integrating"

#### Scenario: Integration failure status
- **WHEN** integration fails after exhausting retries
- **THEN** the change status reads "integration-failed" and the change is treated as terminal (not retried by the monitor loop)
