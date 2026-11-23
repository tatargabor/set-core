# verify-gate — Delta Spec (e2e-gate-diagnostic-context)

## MODIFIED Requirements

### Requirement: No-commit retry does not consume retry budget

Before incrementing `verify_retry_count`, the verifier SHALL check whether the worktree HEAD has changed since `last_gate_commit`. If HEAD equals `last_gate_commit` (no new commits from the agent), the verifier SHALL NOT increment `verify_retry_count`, SHALL log a warning "no-commit retry: agent declared done without new commits", and SHALL re-dispatch the change with the existing retry context.

#### Scenario: Agent commits new work — normal retry
- **WHEN** `handle_change_done()` is called
- **AND** worktree HEAD differs from `last_gate_commit`
- **THEN** `verify_retry_count` SHALL be incremented as before

#### Scenario: Agent declares done without committing — no-commit retry
- **WHEN** `handle_change_done()` is called
- **AND** worktree HEAD equals `last_gate_commit`
- **THEN** `verify_retry_count` SHALL NOT be incremented
- **AND** a warning SHALL be logged
- **AND** the change SHALL be re-dispatched with the same retry context

#### Scenario: No last_gate_commit baseline — treat as normal
- **WHEN** `handle_change_done()` is called
- **AND** `last_gate_commit` is empty or None
- **THEN** the verifier SHALL treat this as a normal retry (increment count)

