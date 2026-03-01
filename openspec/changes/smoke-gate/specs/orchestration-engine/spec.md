## Requirements

### Requirement: Deploy smoke after merge (DELTA)
The orchestrator SHALL optionally run smoke tests against a deployed environment after successful merge.

#### Scenario: Deploy smoke in merge_change
- **WHEN** a change is successfully merged (Case 3 — normal merge)
- **AND** `deploy_smoke_url` is non-empty
- **AND** `smoke_command` is non-empty
- **THEN** the orchestrator SHALL run deploy smoke after `archive_change()` and before removing from merge queue
- **AND** this SHALL NOT block the merge queue processing

### Requirement: Decomposition prompt smoke awareness (DELTA)
The decomposition prompts SHALL include guidance about smoke test coverage.

#### Scenario: Smoke guidance in decomposition
- **WHEN** `smoke_command` is configured (non-empty)
- **THEN** the spec-mode and brief-mode decomposition prompts SHALL include:
  > If the project has smoke tests configured, changes that modify user-facing flows (login, navigation, forms, API endpoints) should include updates to relevant smoke test files as part of the change scope. Organize smoke tests by functional group (auth, CRUD, navigation), not per-change.
