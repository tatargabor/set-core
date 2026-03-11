# orchestration-html-report Delta Spec

## MODIFIED Requirements

### Requirement: Status CSS styling
The HTML reporter SHALL include a `.status-skipped` CSS class with amber/yellow color (`#ffc107`) to visually distinguish skipped changes from merged (green), failed (red), and pending (gray).

#### Scenario: Skipped change in report
- **WHEN** the HTML report is generated
- **AND** a change has status "skipped"
- **THEN** the status SHALL be rendered with CSS class `status-skipped`
- **AND** the color SHALL be `#ffc107` (amber/yellow)

### Requirement: Summary statistics
The HTML report summary SHALL display skipped changes as a separate count, distinct from merged and failed. Format: "N merged, N skipped, N failed".

#### Scenario: Summary with skipped changes
- **WHEN** the HTML report summary is generated
- **AND** 3 changes are merged, 1 is skipped, 1 is failed
- **THEN** the summary SHALL show "3 merged, 1 skipped, 1 failed"

#### Scenario: Summary with no skipped changes
- **WHEN** the HTML report summary is generated
- **AND** no changes have status "skipped"
- **THEN** the skipped count MAY be omitted or shown as "0 skipped"

### Requirement: Skip reason display
When a skipped change has a `skip_reason` field, the reporter SHALL display it alongside the status.

#### Scenario: Skipped with reason
- **WHEN** a skipped change has `skip_reason` set
- **THEN** the report SHALL display the reason text near the status (e.g., as a tooltip or inline text)

#### Scenario: Skipped without reason
- **WHEN** a skipped change has no `skip_reason`
- **THEN** the report SHALL display "skipped" without additional text
