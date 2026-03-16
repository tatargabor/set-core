## ADDED Requirements

### Requirement: Plan validation checks reverse requirement coverage
The `validate_plan()` function SHALL verify that every non-removed requirement in the digest is either assigned to a change (via `requirements[]` or `also_affects_reqs[]`) or explicitly listed in `deferred_requirements[]`. Unassigned and non-deferred requirements SHALL be reported as validation errors.

#### Scenario: All requirements assigned to changes
- **WHEN** `validate_plan()` runs with a digest directory
- **AND** every requirement ID from `requirements.json` appears in at least one change's `requirements[]` or `also_affects_reqs[]`
- **THEN** no coverage-related errors or warnings SHALL be added to the validation result

#### Scenario: Requirement missing from all changes but deferred
- **WHEN** `validate_plan()` runs with a digest directory
- **AND** a requirement ID does not appear in any change
- **AND** the requirement ID appears in `deferred_requirements[]` with a `reason`
- **THEN** a warning SHALL be added: "Deferred requirement: <id> — <reason>"
- **AND** no error SHALL be added for that requirement

#### Scenario: Requirement missing from all changes and not deferred
- **WHEN** `validate_plan()` runs with a digest directory
- **AND** a requirement ID does not appear in any change
- **AND** the requirement ID does NOT appear in `deferred_requirements[]`
- **THEN** an error SHALL be added: "Requirement not covered by any change and not deferred: <id>"

#### Scenario: No digest directory provided
- **WHEN** `validate_plan()` runs without a digest directory
- **THEN** reverse requirement coverage check SHALL be skipped entirely

### Requirement: Plan schema supports deferred_requirements
The orchestration plan JSON SHALL support an optional `deferred_requirements` array at the top level. Each entry SHALL have an `id` (matching a digest requirement ID) and a `reason` (human-readable explanation of why this requirement is deferred).

#### Scenario: Plan with deferred_requirements field
- **WHEN** the planner generates an orchestration plan
- **AND** some requirements are intentionally excluded from this phase
- **THEN** the plan SHALL include a `deferred_requirements` array with entries containing `id` and `reason`

#### Scenario: Plan without deferred_requirements field
- **WHEN** the planner generates an orchestration plan
- **AND** all requirements are assigned to changes
- **THEN** the `deferred_requirements` field MAY be omitted or empty
- **AND** validation SHALL not fail due to the missing field

#### Scenario: Deferred requirement ID not found in digest
- **WHEN** `validate_plan()` processes `deferred_requirements[]`
- **AND** an entry's `id` does not match any requirement ID in the digest `requirements.json`
- **THEN** a warning SHALL be added: "Deferred requirement ID not found in digest: <id>"

### Requirement: Decompose skill requires explicit requirement accounting
The decompose skill prompt SHALL instruct the planner to account for every requirement from the digest: either assign it to a change or defer it with a reason. Silent omission of requirements SHALL be treated as a planning error.

#### Scenario: Planner assigns all requirements
- **WHEN** the decompose skill generates a plan
- **AND** the planner assigns all digest requirements to changes
- **THEN** `deferred_requirements` SHALL be empty or omitted
- **AND** `validate_plan()` SHALL pass with no coverage errors

#### Scenario: Planner defers requirements with reason
- **WHEN** the decompose skill generates a plan
- **AND** the planner determines some requirements belong in a later phase
- **THEN** those requirements SHALL appear in `deferred_requirements` with a reason explaining why
- **AND** `validate_plan()` SHALL pass with coverage warnings but no errors
