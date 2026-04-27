# Per Change Gate Skip Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: gate_hints field on Change dataclass
The Change dataclass SHALL include an optional `gate_hints: dict` field (default None). When present, it SHALL contain gate field names as keys and mode strings as values (e.g., `{"smoke": "skip", "e2e": "warn"}`). The field SHALL be serialized to JSON when not None and deserialized via `from_dict()`.

#### Scenario: gate_hints round-trips through JSON
- **WHEN** a Change with `gate_hints={"smoke": "skip"}` is serialized via `to_dict()` and deserialized via `from_dict()`
- **THEN** the resulting Change SHALL have `gate_hints={"smoke": "skip"}`

#### Scenario: gate_hints None is omitted from JSON
- **WHEN** a Change with `gate_hints=None` is serialized via `to_dict()`
- **THEN** the `gate_hints` key SHALL NOT appear in the output dict

#### Scenario: gate_hints from plan JSON
- **WHEN** a plan JSON change object contains `"gate_hints": {"e2e": "skip"}`
- **THEN** the hydrated Change SHALL have `gate_hints={"e2e": "skip"}`

### Requirement: Plan JSON schema includes gate_hints
The planner JSON output schema templates SHALL include the optional `gate_hints` field with documentation explaining it is for exceptional cases only.

#### Scenario: gate_hints in spec output JSON
- **WHEN** the planning prompt renders the JSON schema example
- **THEN** the schema SHALL include `"gate_hints"` as an optional field with a comment that defaults handle 95% of cases

### Requirement: Post-merge smoke respects GateConfig
The `post_merge_smoke()` function in merger.py SHALL resolve a GateConfig for the change and check `gc.should_run("smoke")` before executing. If smoke is `"skip"`, it SHALL return `"skipped"` immediately.

#### Scenario: Infrastructure change skips smoke
- **WHEN** an infrastructure change completes merge and post_merge_smoke is called
- **THEN** the function SHALL return `"skipped"` without running smoke_command

#### Scenario: Feature change runs smoke normally
- **WHEN** a feature change completes merge and post_merge_smoke is called with a configured smoke_command
- **THEN** the function SHALL execute the smoke pipeline as before

## MODIFIED Requirements

### Requirement: Plan JSON skip_review field
Each change in the plan JSON MAY include a `skip_review` boolean field. When `true`, the verify gate SHALL skip code review for that change. Default SHALL be `false`. The `skip_review` flag SHALL be mapped into GateConfig by `resolve_gate_config()`, setting `review="skip"`.

#### Scenario: Doc-only change skips review
- **WHEN** a change has `"skip_review": true` and completes implementation
- **THEN** the resolved GateConfig SHALL have review=`"skip"`
- **AND** the verify gate SHALL not run the code review step
- **AND** `review_result` SHALL be set to `"skipped"`

#### Scenario: Normal change gets review
- **WHEN** a change has `"skip_review": false` (or not set) and `review_before_merge` is `true`
- **THEN** the resolved GateConfig SHALL have review=`"run"` (from built-in profile)
- **AND** the verify gate SHALL run code review as normal

### Requirement: Plan JSON skip_test field
Each change in the plan JSON MAY include a `skip_test` boolean field. When `true`, the verify gate SHALL skip test execution for that change. Default SHALL be `false`. The `skip_test` flag SHALL be mapped into GateConfig by `resolve_gate_config()`, setting `test="skip"` and `test_files_required=False`.

#### Scenario: Doc-only change skips tests
- **WHEN** a change has `"skip_test": true` and completes implementation
- **THEN** the resolved GateConfig SHALL have test=`"skip"` and test_files_required=`False`
- **AND** the verify gate SHALL not run the test command
- **AND** `test_result` SHALL be set to `"skipped"`

#### Scenario: Normal change runs tests
- **WHEN** a change has `"skip_test": false` (or not set) and a `test_command` is configured
- **THEN** the resolved GateConfig SHALL have test value from the built-in profile for the change_type
- **AND** the verify gate SHALL run tests according to the resolved GateConfig mode
