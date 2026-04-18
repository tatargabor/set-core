# Spec: Design Dispatch Injection (delta)

## MODIFIED Requirements

### Requirement: Design context injected into agent input

The dispatcher SHALL inject design context into the agent's `input.md` by:
1. Calling `profile.copy_design_source_slice(change_name, scope, dest_dir)` to populate `openspec/changes/<change_name>/design-source/` with scope-matched files
2. Calling `profile.get_design_dispatch_context(change_name, scope, project_path)` to obtain the markdown context block (the `change_name` parameter is REQUIRED so the block can reference the exact change directory)
3. Writing the markdown block into a `## Design Source` section of `input.md`

The previous Figma-snapshot pipeline (Design Tokens + Component Hierarchy + Figma Source Files sections) is REPLACED.

#### Scenario: Per-change design-source populated
- **WHEN** dispatching a change to an agent
- **AND** the profile has a non-empty design source (e.g. v0)
- **THEN** `openspec/changes/<change>/design-source/` is populated before `input.md` is written
- **AND** `input.md` contains a `## Design Source` section listing the included files and pointing the agent to the directory

#### Scenario: No design source available
- **WHEN** the profile reports `detect_design_source() == "none"`
- **THEN** `design-source/` is NOT created
- **AND** `input.md` omits the `## Design Source` section
- **AND** dispatch proceeds normally

#### Scenario: design_snapshot_dir parameter removed from dispatch chain
- **WHEN** `dispatch_change()` and `dispatch_ready_changes()` are called
- **THEN** they SHALL NOT accept a `design_snapshot_dir` parameter
- **AND** all call sites (engine, CLI) SHALL be updated to remove the parameter
- **AND** the parameter's previous value (typically `os.getcwd()`) is rederived inside the dispatcher when needed for token extraction

#### Scenario: Retry preserves design-source freshness
- **GIVEN** a change is being re-dispatched after a verifier failure
- **WHEN** the dispatcher prepares input.md for retry
- **THEN** `design-source/` is repopulated (in case scope or manifest changed)
- **AND** stale files from previous dispatch are removed before repopulation

#### Scenario: Context size budget
- **WHEN** `## Design Source` block is written
- **THEN** the markdown block (excluding the design-source files themselves) SHALL NOT exceed 200 lines
- **AND** the actual TSX content lives in design-source/ files (referenced by path), NOT embedded in input.md
