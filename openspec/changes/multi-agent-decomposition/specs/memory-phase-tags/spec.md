## ADDED Requirements

### Requirement: Phase-based memory tagging convention

The orchestrator SHALL use phase-based tags when storing and recalling memories to prevent cross-phase contamination.

#### Scenario: Planning phase memory recall
- **WHEN** the decomposition agent recalls memories
- **THEN** recall SHALL filter by `phase:planning` tag
- **AND** memories tagged `phase:execution` or `phase:verification` SHALL NOT appear in planning recall results

#### Scenario: Execution phase memory recall
- **WHEN** a worker agent is dispatched (proposal.md memory injection)
- **THEN** `orch_recall` SHALL filter by `phase:execution` tag
- **AND** memories tagged `phase:planning` SHALL NOT appear in dispatch recall

#### Scenario: Orchestration phase memory recall
- **WHEN** `auto_replan_cycle()` recalls operational history
- **THEN** recall SHALL filter by `phase:orchestration` tag

#### Scenario: Memory storage with phase tags
- **WHEN** `orch_remember` is called from planning context
- **THEN** the memory SHALL be tagged with `phase:planning`
- **WHEN** `orch_remember` is called from orchestrator operational context
- **THEN** the memory SHALL be tagged with `phase:orchestration`

### Requirement: Memory hygiene before decomposition

The orchestrator SHALL perform a lightweight memory health check before starting decomposition.

#### Scenario: Pre-decomposition hygiene
- **WHEN** `cmd_plan()` is invoked (either API or agent method)
- **THEN** before planning, the orchestrator SHALL:
  1. Run `wt-memory dedup --dry-run` and log duplicate count
  2. Log total memory count and phase tag distribution
  3. Exclude memories tagged `stale:true` from all recall

#### Scenario: Stale memory exclusion
- **WHEN** a memory is tagged `stale:true`
- **THEN** it SHALL NOT appear in any `orch_recall` results
- **AND** a log entry SHALL note how many stale memories were excluded

### Requirement: Phase-filtered orch_recall wrapper

The `orch_recall` function SHALL support phase tag filtering through its existing tags parameter.

#### Scenario: Tags parameter usage for phase filtering
- **WHEN** `orch_recall "$query" $limit "phase:planning"` is called
- **THEN** only memories with `phase:planning` tag SHALL be returned
- **AND** the tag filter SHALL be passed to `wt-memory recall --tags`

#### Scenario: Empty tags parameter (backward compat)
- **WHEN** `orch_recall "$query" $limit ""` is called with empty tags
- **THEN** all memories SHALL be returned regardless of phase tag (current behavior preserved)
