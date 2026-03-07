## MODIFIED Requirements

### Requirement: Memory helper functions
The orchestrator SHALL provide helper functions for saving and recalling memories with consistent tagging, including phase-based filtering.

#### Scenario: orch_remember saves with orchestrator tag
- **WHEN** `orch_remember "content" [type] [extra,tags]` is called
- **THEN** the orchestrator SHALL invoke `wt-memory remember` with tags `source:orchestrator,{extra_tags}`
- **AND** return 0 regardless of wt-memory success/failure (graceful degradation)
- **AND** track operation timing for performance stats

#### Scenario: orch_recall retrieves memories with phase filtering
- **WHEN** `orch_recall "query" [limit] [tag_filter]` is called
- **AND** `tag_filter` is non-empty (e.g., `"phase:planning"`)
- **THEN** the orchestrator SHALL invoke `wt-memory recall` with `--tags "$tag_filter"` in hybrid mode
- **AND** return plain text (max 2000 chars) or empty string if wt-memory unavailable
- **AND** memories tagged `stale:true` SHALL be excluded from results

#### Scenario: orch_recall with empty tag filter (backward compat)
- **WHEN** `orch_recall "query" [limit] ""` is called with empty tag_filter
- **THEN** all memories SHALL be returned regardless of phase tag (current behavior preserved)
- **AND** memories tagged `stale:true` SHALL still be excluded

## ADDED Requirements

### Requirement: Memory hygiene before decomposition
The orchestrator SHALL perform a lightweight memory health check before starting any plan decomposition.

#### Scenario: Pre-decomposition hygiene check
- **WHEN** `cmd_plan()` is invoked (either API or agent method)
- **THEN** before planning, the orchestrator SHALL:
  1. Run `wt-memory dedup --dry-run` and log the duplicate count
  2. Log total memory count and phase tag distribution
  3. Note stale memory count for the run log
- **AND** these checks SHALL be best-effort (failure does not block planning)

### Requirement: Phase-tagged memory storage in orchestrator
The orchestrator SHALL tag memories with the appropriate phase when storing them.

#### Scenario: Planning phase memory tagging
- **WHEN** `orch_remember` is called during decomposition (from planner context)
- **THEN** the memory SHALL automatically include `phase:planning` in tags

#### Scenario: Orchestration phase memory tagging
- **WHEN** `orch_remember` is called during operational orchestrator events (replan, dispatch decisions)
- **THEN** the memory SHALL automatically include `phase:orchestration` in tags

#### Scenario: Execution phase memory tagging at dispatch
- **WHEN** memory context is injected into proposal.md during `dispatch_change()`
- **THEN** `orch_recall` SHALL use `phase:execution` tag filter
