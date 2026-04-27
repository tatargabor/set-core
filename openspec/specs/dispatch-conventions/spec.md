# Dispatch Conventions Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Inject read-first instructions in dispatch context
The dispatcher SHALL include a "read-first" instruction block in the dispatch context telling agents to read relevant source files before writing code. The instruction SHALL reference the actual files present in the project (e.g., `prisma/schema.prisma`, `src/components/`).

#### Scenario: Prisma project gets schema read instruction
- **WHEN** dispatcher builds input content for a change AND `prisma/schema.prisma` exists
- **THEN** the dispatch context SHALL include: "Before writing any Prisma code, read `prisma/schema.prisma`"

#### Scenario: Component directory instruction
- **WHEN** dispatcher builds input content AND a components directory exists (e.g., `src/components/`)
- **THEN** the dispatch context SHALL include: "Before creating a new component, check existing ones in the components directory"

#### Scenario: Read-first adapts to project structure
- **WHEN** the project uses a different directory layout (e.g., `app/components/` instead of `src/components/`)
- **THEN** the instruction SHALL reference the actual paths found in the project

### Requirement: Inject project conventions document in dispatch context
The dispatcher SHALL include a concise conventions summary (~500 bytes) in the dispatch context, derived from `conventions.json` (if present) and auto-detected framework patterns.

#### Scenario: Conventions from digest
- **WHEN** `conventions.json` exists in the digest directory
- **THEN** the dispatch context SHALL include a formatted conventions section with key patterns (auth, i18n, CSS, components, data access)

#### Scenario: No conventions available
- **WHEN** no `conventions.json` exists AND no framework patterns are detected
- **THEN** the dispatcher SHALL skip conventions injection without error

### Requirement: Conventions injected in _build_input_content
The conventions and read-first instructions SHALL be added within the existing `_build_input_content()` function in dispatcher.py, not as a separate CLAUDE.md section. This keeps them scoped to the specific change dispatch.

#### Scenario: Conventions appear in input.md
- **WHEN** a change is dispatched to an agent
- **THEN** the generated `input.md` SHALL contain the conventions and read-first sections alongside existing context (scope, spec files, design tokens)

#### Scenario: Conventions do not duplicate CLAUDE.md content
- **WHEN** the schema digest is already in CLAUDE.md AND conventions reference schema patterns
- **THEN** the conventions section SHALL NOT repeat schema field listings but MAY reference "see Project Schema section in CLAUDE.md"
