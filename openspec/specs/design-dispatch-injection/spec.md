## MODIFIED Requirements

### Requirement: Design context extraction for dispatch

The dispatcher SHALL extract design context from `design-snapshot.md` when dispatching a change. The `design_snapshot_dir` parameter SHALL be propagated from `dispatch_ready_changes()` to `dispatch_change()`.

#### Scenario: design_snapshot_dir propagated through dispatch chain
- **WHEN** `dispatch_ready_changes()` is called with a `design_snapshot_dir` parameter
- **THEN** each `dispatch_change()` call receives the same `design_snapshot_dir` value
- **AND** `design_context_for_dispatch()` is called with the correct snapshot directory

#### Scenario: Engine passes design_snapshot_dir to dispatch
- **WHEN** the orchestration engine calls `dispatch_ready_changes()` after planning
- **THEN** it passes `design_snapshot_dir=os.getcwd()` (project root)
- **AND** the snapshot fetched by the planner is accessible to the dispatcher

#### Scenario: Dispatch without design_snapshot_dir (backwards compatible)
- **WHEN** `dispatch_ready_changes()` is called without `design_snapshot_dir`
- **THEN** it defaults to `"."` (current working directory)
- **AND** the existing behavior is preserved

#### Scenario: CLI callers use cwd as default
- **WHEN** `dispatch_change()` or `dispatch_ready_changes()` is called from the CLI (`cli.py`)
- **THEN** `design_snapshot_dir` defaults to `os.getcwd()`
- **AND** no new CLI argument is required (CLI always runs from project root)
