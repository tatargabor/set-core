## MODIFIED Requirements

### Requirement: Dispatch change to worktree
The system SHALL create a worktree via `set-new`, bootstrap it, prune orchestrator context, build proposal.md with scope/memory/project-knowledge/sibling context, and launch set-loop. Token counters SHALL be reset on fresh dispatch. If worktree already exists, stale loop state SHALL be cleaned up. When the change has `ikp_packs`, the dispatcher SHALL inject IKP rule files into the worktree and add an IKP summary section to input.md.

#### Scenario: Dispatch with IKP packs
- **WHEN** dispatching a change that has `ikp_packs: ["billingo"]`
- **AND** `has_ikp_pipeline()` returns True
- **THEN** the dispatcher SHALL call `ikp_bridge.inject_rules_for_change()` after design deployment
- **AND** SHALL include IKP summary in the input.md assembly
- **AND** SHALL log the injected pack names at INFO level

#### Scenario: Dispatch without IKP
- **WHEN** dispatching a change with no `ikp_packs`
- **THEN** the dispatch flow SHALL be unchanged from the existing behavior
