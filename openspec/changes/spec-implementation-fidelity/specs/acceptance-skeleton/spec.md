## ADDED Requirements

### Requirement: FF skill generates acceptance criteria from scenarios
The ff-change skill SHALL extract WHEN/THEN scenarios from delta specs and generate an Acceptance Criteria section at the bottom of tasks.md. Each acceptance criterion is a checkbox item linked to its source scenario and requirement.

#### Scenario: Spec with scenarios generates acceptance criteria
- **WHEN** the ff-change skill creates tasks.md
- **AND** delta specs contain scenarios with WHEN/THEN format
- **THEN** tasks.md SHALL include an `## Acceptance Criteria (from spec scenarios)` section
- **AND** each scenario SHALL become a checkbox item: `- [ ] AC-N: WHEN <condition> THEN <outcome> [REQ: <name>, scenario: <scenario-name>]`

#### Scenario: Spec without scenarios
- **WHEN** the ff-change skill creates tasks.md
- **AND** delta specs contain requirements but no WHEN/THEN scenarios
- **THEN** the Acceptance Criteria section SHALL be omitted
- **AND** no error SHALL be raised

#### Scenario: Multiple specs with scenarios
- **WHEN** the ff-change skill creates tasks.md
- **AND** multiple delta spec files contain scenarios
- **THEN** all scenarios from all spec files SHALL be included in the Acceptance Criteria section
- **AND** they SHALL be grouped by requirement name

### Requirement: Verify treats unchecked acceptance criteria as CRITICAL
The verify-change skill SHALL parse the Acceptance Criteria section and treat unchecked items with the same severity as unchecked implementation tasks.

#### Scenario: All acceptance criteria checked
- **WHEN** the verify skill parses tasks.md
- **AND** all `AC-N` items under Acceptance Criteria are checked (`- [x]`)
- **THEN** the completeness report SHALL include "Acceptance Criteria: N/N passed"

#### Scenario: Unchecked acceptance criteria
- **WHEN** the verify skill parses tasks.md
- **AND** one or more `AC-N` items are unchecked (`- [ ]`)
- **THEN** it SHALL report a CRITICAL issue: "Acceptance criterion not met: <AC description>"
- **AND** the recommendation SHALL reference the source scenario and requirement

#### Scenario: No acceptance criteria section in tasks.md
- **WHEN** the verify skill parses tasks.md
- **AND** no Acceptance Criteria section exists
- **THEN** acceptance criteria checking SHALL be skipped
- **AND** the report SHALL note "No acceptance criteria section — skipping AC check"
