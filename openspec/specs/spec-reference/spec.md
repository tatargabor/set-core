# Spec Reference Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Spec reference in proposal.md

The orchestrator SHALL include a `## Source Spec` section in generated proposal.md files, giving worker agents a reference to the original spec document.

#### Scenario: Spec-mode dispatch with spec reference
- **WHEN** a change is dispatched and the input mode is `spec`
- **THEN** the generated `proposal.md` SHALL include a `## Source Spec` section containing:
  - `Path`: the spec file path relative to project root
  - `Section`: the relevant section from the spec (from `roadmap_item`)
  - A hint that the full spec is readable via `cat <path>`

#### Scenario: Brief-mode dispatch (no spec reference)
- **WHEN** a change is dispatched and the input mode is `brief`
- **THEN** no `## Source Spec` section SHALL be added (brief mode has no single spec document)

#### Scenario: Worker agent spec access
- **WHEN** a worker agent reads proposal.md and encounters the `## Source Spec` section
- **THEN** the agent SHALL be able to read the referenced file directly (it exists in the worktree via git)
- **AND** the agent decides when to consult the spec — it is NOT loaded into context automatically
