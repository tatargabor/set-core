## ADDED Requirements

## IN SCOPE
- Parsing JOURNEY-TEST-PLAN.md into structured test case data
- Parsing Playwright stdout for per-test pass/fail results
- Cross-referencing plan entries with test results
- Storing TestCoverage in orchestration state
- Detecting coverage gaps (scenarios without tests)
- Detecting non-testable ACs (marked exempt)

## OUT OF SCOPE
- Modifying how the acceptance-tests agent writes tests or the plan
- Real-time test streaming or live test progress
- Per-change test traceability (only acceptance-tests change tracked)
- Playwright JSON reporter configuration (parse stdout first)

### Requirement: Parse JOURNEY-TEST-PLAN.md into test cases
The system SHALL parse the test plan file produced by the acceptance-tests agent, extracting REQ IDs, risk levels, test cases with Given/When/Then, and test file references.

#### Scenario: Standard plan format
- **WHEN** `tests/e2e/JOURNEY-TEST-PLAN.md` exists after acceptance-tests merge
- **AND** it contains `## REQ-XXX: Title [RISK]` headers with `- [x]`/`- [ ]` test case lines
- **THEN** the parser SHALL extract one TestCase per checkbox line
- **AND** each TestCase SHALL have: req_id, risk, scenario_slug (derived from text), test_file, test_name, category

#### Scenario: Test file reference extraction
- **WHEN** a test case line is followed by `→ filename.spec.ts: "test name"`
- **THEN** the parser SHALL populate test_file and test_name on the TestCase

#### Scenario: Non-testable requirement
- **WHEN** a requirement header contains `[NON-TESTABLE]`
- **THEN** the parser SHALL add the REQ ID to the non_testable_reqs list
- **AND** it SHALL NOT count as a coverage gap

#### Scenario: Missing or malformed plan file
- **WHEN** the plan file does not exist or cannot be parsed
- **THEN** the system SHALL log a warning
- **AND** store an empty TestCoverage with coverage_pct = 0

### Requirement: Parse E2E test results via profile
The system SHALL use the project type profile's `parse_test_results()` method to parse E2E gate stdout into per-test pass/fail data. This keeps test framework parsing in the appropriate module (e.g., Playwright parsing in web module, pytest parsing in Python module).

#### Scenario: Profile provides test result parser
- **WHEN** the active profile implements `parse_test_results(stdout: str) -> dict[tuple[str,str], str]`
- **THEN** the system SHALL call it to get {(file, name): "pass"|"fail"} mapping

#### Scenario: Profile does not implement parser
- **WHEN** the active profile's `parse_test_results()` returns an empty dict (default ABC)
- **THEN** the system SHALL fall back to binary pass/fail from gate result
- **AND** individual test case results SHALL remain None

#### Scenario: Match results to plan entries
- **WHEN** both plan entries and parsed results are available
- **THEN** the system SHALL match them by test_file + test_name (case-insensitive, whitespace-tolerant)
- **AND** populate TestCase.result with "pass" or "fail"
- **AND** unmatched plan entries SHALL have result = None

### Requirement: Store test coverage in state
After parsing, the system SHALL store a TestCoverage object in `state.extras["test_coverage"]`.

#### Scenario: Coverage calculation
- **WHEN** test coverage is calculated
- **THEN** covered_reqs SHALL contain REQ IDs that have at least one test case with a test file reference
- **AND** uncovered_reqs SHALL contain REQ IDs from the digest that have zero test cases
- **AND** coverage_pct SHALL be `len(covered_reqs) / (len(covered_reqs) + len(uncovered_reqs)) * 100`
- **AND** non_testable_reqs SHALL be excluded from the coverage calculation

#### Scenario: Post-merge trigger
- **WHEN** the acceptance-tests change merges successfully
- **THEN** the merge pipeline SHALL trigger test coverage parsing
- **AND** store the result in state before the orchestration completes

### Requirement: Coverage gap detection
The system SHALL identify requirements that have no test coverage and surface them.

#### Scenario: Uncovered requirement
- **WHEN** a digest requirement has no matching test case in the plan
- **AND** it is not marked non-testable
- **THEN** it SHALL appear in uncovered_reqs

#### Scenario: Partially covered requirement
- **WHEN** a requirement has scenarios but only some have test cases
- **THEN** the covered scenario count and total scenario count SHALL both be available
- **AND** the requirement SHALL appear in covered_reqs (partial coverage counts as covered)
