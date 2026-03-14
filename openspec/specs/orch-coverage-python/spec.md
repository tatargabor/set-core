## ADDED Requirements

### Requirement: Python coverage tracking
The Python orchestration system SHALL track requirement coverage status, updating it as changes are merged and providing final coverage validation.

#### Scenario: Update coverage after merge
- **WHEN** a change is successfully merged
- **THEN** `digest.update_coverage_status()` SHALL mark all requirements mapped to that change as "covered"
- **AND** the update SHALL be written to the digest output directory

#### Scenario: Final coverage check
- **WHEN** orchestration reaches terminal state
- **THEN** `digest.final_coverage_check()` SHALL read the digest requirements and coverage mapping
- **AND** return a summary of covered vs uncovered requirements
- **AND** the summary SHALL be included in the completion email

### Requirement: Python coverage population
The Python planning system SHALL populate coverage mapping when a new plan is created.

#### Scenario: Coverage populated during plan enrichment
- **WHEN** `planner.enrich_plan_metadata()` runs on a new plan
- **THEN** it SHALL call `digest.populate_coverage()` to map plan changes to requirements
- **AND** it SHALL call `digest.check_coverage_gaps()` to warn about uncovered requirements
