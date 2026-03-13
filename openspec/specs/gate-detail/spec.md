## ADDED Requirements

### Requirement: Gate output expandable detail
When a user clicks a gate badge (T/B/R/S) or the Gates cell in the ChangeTable, the row expands inline to show full gate output text.

#### Scenario: Expand gate detail for a completed change
- **WHEN** user clicks on a gate badge or the Gates cell of a change row
- **THEN** the row expands below to show collapsible sections for each gate that has output
- **THEN** each section shows the gate name, result (pass/fail/skip), and full output text in a scrollable monospace block
- **THEN** clicking again collapses the detail

#### Scenario: Gate with no output
- **WHEN** a gate has a result but no output text (e.g., `test_result: "skip"`, `test_output: ""`)
- **THEN** the section shows the result badge but displays "No output" in muted text

#### Scenario: Multiple gates with output
- **WHEN** a change has output for build, test, review, and smoke
- **THEN** all four sections are shown, each independently collapsible
- **THEN** the first non-pass gate is expanded by default (if any), otherwise all collapsed

### Requirement: Gate output fields in API
The state API must include gate output fields in the change data.

#### Scenario: State enrichment includes gate outputs
- **WHEN** the `/api/{project}/state` endpoint returns change data
- **THEN** each change includes `build_output`, `test_output`, `smoke_output`, `review_output` string fields (if present in state file)
- **THEN** the `gate_total_ms` and individual `gate_build_ms`, `gate_test_ms`, `gate_review_ms`, `gate_verify_ms` timing fields are included
