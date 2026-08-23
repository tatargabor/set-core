## MODIFIED Requirements

### Requirement: Review findings section
The LearningsPanel SHALL display review findings with recurring patterns highlighted and per-finding drill-down.

#### Scenario: Recurring patterns banner
- **WHEN** review findings contain patterns appearing in 2+ changes
- **THEN** a "Recurring Patterns" subsection shows each pattern with its occurrence count

#### Scenario: Finding list
- **WHEN** review findings are loaded
- **THEN** findings display as expandable rows with severity badge (CRITICAL/HIGH/MEDIUM), summary text, and change name

#### Scenario: Expanded finding
- **WHEN** the user expands a finding row
- **THEN** the detail shows file path, line number, fix recommendation, and attempt number
- **AND** the file path shown SHALL be the resolved absolute path the API supplies, so it can
  be opened from where the reader is standing

#### Scenario: Expanded finding with no resolved path
- **WHEN** the API supplies no resolved path for a finding
- **THEN** the detail SHALL show the stored relative path rather than an empty field
