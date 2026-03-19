# sentinel-e2e-mode Specification

## Purpose
Extends the sentinel supervisor with operational intelligence from E2E runs and an E2E-specific Tier 3 mode that allows framework bug fixes mid-run.

## IN SCOPE
- Expanded Tier 1 (defer) list with known false-positive patterns
- Token stuck detection for changes exceeding budget with no commits
- Dependency deadlock detection for pending changes blocked by failed deps
- E2E Tier 3 mode: framework fix + deploy authority with strict scope boundary

## OUT OF SCOPE
- Changing Tier 1/2 core logic (additive only)
- Auto-fixing dependency deadlocks (report only)
- Consumer project code modifications (always forbidden)

### Requirement: expected-pattern-awareness
The sentinel Tier 1 list SHALL include known false-positive patterns with explanations, so the sentinel does not escalate expected transient states.

#### Scenario: Post-merge build failure from stale codegen
- **WHEN** sentinel observes a build failure immediately after a merge
- **THEN** sentinel SHALL recognize this as expected (post_merge_command handles codegen) and defer — not escalate

#### Scenario: Watchdog no-progress on freshly dispatched change
- **WHEN** sentinel sees a watchdog warning within 2 minutes of a change dispatch
- **THEN** sentinel SHALL recognize the startup grace period and defer

#### Scenario: Long MCP fetch during design preflight
- **WHEN** sentinel observes stale state during a design fetch (4-5 min)
- **THEN** sentinel SHALL check for heartbeat events and defer if heartbeats are present

### Requirement: token-stuck-detection
The sentinel poll script SHALL detect changes that have consumed >500K tokens without a recent commit (>30 min) and emit a WARNING:token_stuck event.

#### Scenario: Change exceeds token budget with no progress
- **WHEN** a running change has tokens_used > 500000 and last_commit_at is null or older than 30 minutes
- **THEN** sentinel SHALL emit WARNING:token_stuck and escalate to user on first detection

#### Scenario: Token stuck in completion report
- **WHEN** sentinel produces a completion report
- **THEN** the report SHALL include per-change token breakdown with stuck flags for changes that exceeded 500K tokens

### Requirement: dependency-deadlock-detection
The sentinel poll script SHALL detect pending changes whose dependencies have all failed, and report the deadlock to the user.

#### Scenario: All dependencies of a pending change are failed
- **WHEN** a change has status "pending" and all entries in its depends_on array have status "failed"
- **THEN** sentinel SHALL emit WARNING:deadlocked and report the specific change names and failed dependencies to the user

#### Scenario: Deadlock does not auto-resolve
- **WHEN** a dependency deadlock is detected
- **THEN** sentinel SHALL NOT automatically modify state — it reports and the user decides whether to clear deps or mark as failed

### Requirement: e2e-tier3-framework-fix-authority
In E2E mode, the sentinel SHALL have Tier 3 authority to fix set-core framework bugs and deploy them to the running test environment.

#### Scenario: Framework bug detected during E2E monitoring
- **WHEN** sentinel identifies a framework bug (dispatch error, path resolution, state machine bug) during E2E monitoring
- **THEN** sentinel SHALL fix the bug in the set-core repo, commit, deploy via set-project init, sync worktrees, and restart

#### Scenario: Scope boundary — set-core only
- **WHEN** sentinel is fixing a framework bug in E2E mode
- **THEN** sentinel SHALL only modify files in the set-core repo (bin/, lib/, .claude/, docs/) and MUST NOT modify consumer project source code

#### Scenario: Scope boundary — no branch merging
- **WHEN** sentinel is in E2E mode
- **THEN** sentinel MUST NOT merge branches, resolve merge conflicts, or edit orchestration-state.json directly

#### Scenario: Scope boundary — no quality gate weakening
- **WHEN** sentinel is in E2E mode
- **THEN** sentinel MUST NOT remove or weaken smoke_command, test_command, merge_policy, review_before_merge, or max_verify_retries

#### Scenario: Fix logging
- **WHEN** sentinel fixes a framework bug in E2E mode
- **THEN** sentinel SHALL log the fix as a finding via set-sentinel-finding add with the commit hash
