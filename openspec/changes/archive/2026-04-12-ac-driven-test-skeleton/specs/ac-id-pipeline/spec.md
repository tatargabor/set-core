# AC-ID Pipeline

## MODIFIED Requirements

### Requirement: AC-ID generation in digest
The digest SHALL generate explicit AC-IDs for each acceptance criterion in the format `REQ-XXX-NNN:AC-M` where M is the ordinal position (1-based).

#### Scenario: requirements.json contains ac_id per criterion
- **WHEN** the digest extracts acceptance_criteria for a requirement
- **THEN** each criterion object has an `ac_id` field in format `REQ-XXX-NNN:AC-M`
- **AND** the ac_id is stable (same AC text always gets same ordinal)

#### Scenario: Backwards compatibility with old requirements.json
- **WHEN** requirements.json has acceptance_criteria as plain string array (no ac_id)
- **THEN** the pipeline generates AC-IDs from array position at consumption time

### Requirement: AC-ID in test plan entries
The test plan generator SHALL include `ac_id` in each TestPlanEntry, propagated from requirements.json.

#### Scenario: test-plan.json entries have ac_id
- **WHEN** generate_test_plan() creates entries from requirements
- **THEN** each TestPlanEntry has `ac_id` field (e.g., `REQ-NAV-001:AC-1`)
- **AND** the ac_id is carried through to TestCase objects

#### Scenario: TestPlanEntry dataclass has ac_id field
- **WHEN** TestPlanEntry is serialized to/from dict
- **THEN** ac_id field is preserved in both directions

### Requirement: AC-ID in test skeleton
The skeleton generator SHALL use AC-ID as the stable test block identifier, not scenario text.

#### Scenario: Skeleton test blocks use AC-ID prefix
- **WHEN** generate_skeleton() creates a test file
- **THEN** each test block starts with the AC-ID: `test('REQ-NAV-001:AC-1 — Header visible on all pages', ...)`
- **AND** the AC-ID is parseable by regex `REQ-[A-Z]+-\d+:AC-\d+`

#### Scenario: Skeleton describe blocks group by REQ-ID
- **WHEN** a requirement has multiple ACs
- **THEN** the skeleton groups them under `test.describe('REQ-NAV-001: Header with nav links', ...)`
- **AND** each test within the describe has a unique AC-ID

### Requirement: AC-ID based coverage binding
The coverage engine SHALL bind tests to ACs by AC-ID first, falling back to slug matching only when AC-ID is absent.

#### Scenario: Phase 0 — AC-ID extraction and binding
- **WHEN** a test name contains `REQ-XXX-NNN:AC-M` pattern
- **THEN** the coverage engine extracts the AC-ID
- **AND** binds the test directly to the matching TestCase by ac_id
- **AND** skips slug-based matching for this test

#### Scenario: Fallback to slug matching
- **WHEN** a test name contains REQ-ID but no AC-ID
- **THEN** the coverage engine falls back to current slug matching
- **AND** logs a warning about missing AC-ID

#### Scenario: Coverage output includes ac_id
- **WHEN** TestCoverage is serialized
- **THEN** each test_case entry includes the `ac_id` field
- **AND** the dashboard can use ac_id for precise AC-level display

### Requirement: Dashboard AC-ID display
The dashboard SHALL use AC-ID for matching test results to acceptance criteria.

#### Scenario: ACPanel matches by ac_id
- **WHEN** the AC tab displays scenarios for a requirement
- **THEN** it matches test_cases by `ac_id` field first
- **AND** falls back to `scenario_slug` match if ac_id absent

#### Scenario: E2E tab shows AC-ID in test names
- **WHEN** the E2E tab displays test results
- **THEN** tests with AC-IDs show them visibly (e.g., highlighted or badged)
