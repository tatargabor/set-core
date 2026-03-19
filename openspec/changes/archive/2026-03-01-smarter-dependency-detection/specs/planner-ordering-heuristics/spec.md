## ADDED Requirements

### Requirement: Change-type classification in decomposition prompt
The decomposition prompt SHALL instruct Claude to classify each change by type and apply ordering rules.

#### Scenario: Change types defined
- **WHEN** Claude decomposes a spec into changes
- **THEN** it considers these change types for ordering: infrastructure (test/build setup), schema (DB migrations), foundational (auth, shared types, base components), feature (new functionality), cleanup-before (refactor/rename that precedes features), cleanup-after (dead code, cosmetic)

#### Scenario: Cleanup-before ordering
- **WHEN** a change involves refactoring, renaming, reorganizing, or cleaning up code AND other changes add features in the same area
- **THEN** the cleanup change has no dependencies, and the feature changes list the cleanup in their `depends_on`

#### Scenario: Schema-first ordering
- **WHEN** a change creates or modifies DB schema/migrations AND other changes build on those tables
- **THEN** data-layer changes depend on schema changes

#### Scenario: Foundational-first ordering
- **WHEN** a change implements auth, shared types, or base infrastructure AND other changes consume those
- **THEN** consumer changes depend on the foundational change

### Requirement: Respect spec-level dependency hints
The decomposition prompt SHALL explicitly instruct Claude to preserve dependency annotations from the input spec.

#### Scenario: Spec contains dependency annotations
- **WHEN** the input spec contains text like "depends_on: X" or "requires X to be done first" or "after X is complete"
- **THEN** the decomposed changes preserve these as `depends_on` entries in the output JSON

#### Scenario: Spec has no dependency hints
- **WHEN** the input spec has no explicit dependency annotations
- **THEN** Claude infers dependencies from the ordering heuristics above

### Requirement: Ordering heuristic rules added to prompt text
The prompt text in `set-orchestrate` SHALL include ordering heuristic rules.

#### Scenario: Prompt text includes ordering rules
- **WHEN** the decomposition prompt is built (both spec-mode and brief-mode)
- **THEN** it includes ~10 lines of ordering heuristic rules after the existing dependency rule
