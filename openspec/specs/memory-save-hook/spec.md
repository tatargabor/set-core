# Memory Save Hook Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Unconditional Code Map Generation
The code-map safety net in `set-hook-memory-save` SHALL fire for every new commit regardless of whether design.md extraction already ran for that change name. The code-map block MUST NOT be gated behind the design-marker `continue` guard.

#### Scenario: Code map generated even without design.md
- **WHEN** a commit is detected for change "foo" but no `design.md` exists
- **THEN** the code-map safety net SHALL still check and potentially generate a code map

#### Scenario: Code map independent of design marker
- **WHEN** a commit is detected for change "bar" and `$DESIGN_MARKER` already contains "bar"
- **THEN** the code-map block SHALL still evaluate (using its own `$CODEMAP_MARKER`)

#### Scenario: No duplicate code maps
- **WHEN** `$CODEMAP_MARKER` already contains the change name
- **THEN** the code-map block SHALL skip (existing dedup behavior preserved)

### Requirement: Recall-Then-Verify Pattern
The benchmark CLAUDE.md template for memory-enabled runs (`with-memory.md`) SHALL include an instruction that recalled code maps and implementation details MUST be verified against current codebase state before acting on them.

#### Scenario: Recall-then-verify in CLAUDE.md
- **WHEN** `with-memory.md` is used as the CLAUDE.md template for Run B
- **THEN** the Proactive Memory section SHALL contain a paragraph instructing the agent to grep/verify recalled details before trusting them

#### Scenario: Instruction wording
- **WHEN** the agent recalls a code-map memory (e.g., "product-catalog code map: src/app/products/page.tsx")
- **THEN** the CLAUDE.md instruction SHALL direct it to verify the file exists and contains the expected pattern before assuming correctness
