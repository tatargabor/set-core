## ADDED Requirements

### Requirement: Dispatch context written to input.md
When dispatching a change, the orchestrator SHALL write all dispatcher-generated context to `openspec/changes/<name>/input.md` in the worktree, separate from `proposal.md`.

#### Scenario: input.md created on dispatch
- **WHEN** `dispatch_change("cart-actions")` runs
- **THEN** `openspec/changes/cart-actions/input.md` SHALL be created in the worktree
- **AND** it SHALL contain: Scope, Project Context, Sibling Changes, Design Context sections
- **AND** `proposal.md` SHALL NOT contain injected orchestration context

#### Scenario: Retry context appended to input.md
- **WHEN** a change is retried with `retry_context` set in state extras
- **THEN** the retry context SHALL be appended to `input.md` under a `## Retry Context` section
- **AND** `proposal.md` SHALL NOT have retry context appended to it

#### Scenario: input.md missing (legacy or manual dispatch)
- **WHEN** a worktree has no `input.md` (manually dispatched or pre-existing worktree)
- **THEN** the ff skill SHALL proceed without it, treating the change as having no injected context

#### Scenario: input.md committed with archive
- **WHEN** a change is archived to `openspec/changes/archive/YYYY-MM-DD-<name>/`
- **THEN** `input.md` SHALL be present in the archived directory alongside proposal.md, design.md, specs/, tasks.md
- **AND** it SHALL NOT be in `.gitignore`

### Requirement: ff skill reads input.md as first step
The `/opsx:ff` skill SHALL read `input.md` as the first step of artifact creation, before writing any artifact.

#### Scenario: ff pre-read phase
- **WHEN** the agent runs `/opsx:ff <change-name>`
- **AND** `input.md` exists in the change directory
- **THEN** the agent SHALL read `input.md` first
- **AND** identify which existing codebase files are relevant to the change scope
- **AND** read those files before creating proposal.md, design.md, specs/, tasks.md

#### Scenario: ff without input.md
- **WHEN** the agent runs `/opsx:ff <change-name>`
- **AND** `input.md` does not exist
- **THEN** the agent SHALL proceed with artifact creation using available context (CLAUDE.md, codebase exploration)
- **AND** SHALL NOT fail or wait for input.md
