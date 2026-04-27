# Design Dispatch Injection Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.
## Requirements
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

### Requirement: Dispatch context includes design information
The dispatcher SHALL inject design context into the agent's proposal. The design context SHALL now include three sections (previously two): Design Tokens, Relevant Component Hierarchies, AND matched Figma Source Files.

#### Scenario: Figma sources available for UI change
- **WHEN** dispatching a change with UI scope and `docs/figma-raw/*/sources/` exists
- **THEN** the proposal SHALL contain Design Tokens, matched Component Hierarchy, AND matched Figma source file contents
- **AND** total design context SHALL NOT exceed 500 lines

#### Scenario: No figma-raw sources (only snapshot)
- **WHEN** dispatching a change with `design-snapshot.md` but no `sources/` directory
- **THEN** the proposal SHALL contain Design Tokens and Component Hierarchy only (existing behavior unchanged)

#### Scenario: Infrastructure change with no UI scope
- **WHEN** dispatching a change with scope containing only "prisma", "jest", "config" terms
- **THEN** no source files SHALL be injected (only tokens if design snapshot exists)

### Requirement: Context budget allocation
The total design context injected into proposals SHALL respect a 500-line budget allocated as: Design Tokens (~100 lines), Component Hierarchy (max 100 lines), Source Files (max 300 lines).

#### Scenario: All three sections present
- **WHEN** tokens are 80 lines, hierarchy is 120 lines, sources are 400 lines
- **THEN** hierarchy SHALL be truncated to 100 lines and sources to 300 lines
- **AND** total SHALL NOT exceed 500 lines

### Requirement: design_components autopopulated into Focus files
The dispatcher SHALL include the change's `design_components` in the `## Focus files for this change` section of the agent's `input.md`. A directive line SHALL precede the listing, instructing the agent to mount these components from the design source rather than reimplementing them.

#### Scenario: Focus files contain design_components paths
- **WHEN** dispatcher writes `input.md` for a change with `design_components: ["v0-export/components/search-palette.tsx", "v0-export/components/site-header.tsx"]`
- **THEN** the input.md `## Focus files for this change` section contains both paths
- **AND** the section is preceded by: "**Mount these components from the design source. DO NOT create parallel implementations under different names.**"

#### Scenario: Empty design_components produces no design Focus mention
- **WHEN** a change has `design_components: []`
- **THEN** the input.md does not include design Focus entries
- **AND** other Focus files (from existing logic) appear normally

#### Scenario: Design_components appended to existing Focus list
- **GIVEN** existing Focus files logic produces a list including `v0-export/lib/utils.ts`
- **WHEN** `design_components` adds `v0-export/components/search-palette.tsx`
- **THEN** the merged Focus files list contains both, deduplicated

