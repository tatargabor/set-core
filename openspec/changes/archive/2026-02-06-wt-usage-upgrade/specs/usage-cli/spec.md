## ADDED Requirements

### Requirement: CLI time range selection
The `wt-usage` command SHALL support time range flags to query usage over different periods.

#### Scenario: Default 5-hour window
- **WHEN** user runs `wt-usage` with no time flags
- **THEN** the output shows token usage for the last 5 hours

#### Scenario: Today's usage
- **WHEN** user runs `wt-usage --today`
- **THEN** the output shows token usage since midnight UTC of the current day

#### Scenario: Weekly usage
- **WHEN** user runs `wt-usage --week`
- **THEN** the output shows token usage for the last 7 days

#### Scenario: Monthly usage
- **WHEN** user runs `wt-usage --month`
- **THEN** the output shows token usage for the last 30 days

### Requirement: CLI cost estimation
The `wt-usage` command SHALL display estimated USD cost when requested.

#### Scenario: Cost flag shows estimated cost
- **WHEN** user runs `wt-usage --cost`
- **THEN** the output includes an estimated USD cost prefixed with "~$"
- **AND** cost is calculated from per-model token prices

#### Scenario: Cost combined with time range
- **WHEN** user runs `wt-usage --today --cost`
- **THEN** the output shows today's token usage with estimated cost

### Requirement: CLI session key login
The `wt-usage` command SHALL provide a `--login` flag for session key acquisition.

#### Scenario: Login flow opens browser
- **WHEN** user runs `wt-usage --login`
- **THEN** the default browser opens to `https://claude.ai`
- **AND** the terminal displays instructions to copy sessionKey from DevTools
- **AND** the terminal prompts for the session key

#### Scenario: Session key saved after login
- **WHEN** user pastes a valid session key
- **THEN** the key is saved to `~/.config/set-core/claude-session.json`
- **AND** a test API call is made to verify the key works
- **AND** success or failure is reported

#### Scenario: Login flow on macOS
- **WHEN** user runs `wt-usage --login` on macOS
- **THEN** the browser is opened via `open` command

#### Scenario: Login flow on Linux
- **WHEN** user runs `wt-usage --login` on Linux
- **THEN** the browser is opened via `xdg-open` command

### Requirement: CLI API-enhanced output
When a valid session key is available, the CLI SHALL display exact usage percentages and reset times.

#### Scenario: Output with session key
- **WHEN** user runs `wt-usage` and a valid session key exists
- **THEN** the output includes exact session percentage and reset time
- **AND** the output includes exact weekly percentage and reset time

#### Scenario: Output without session key
- **WHEN** user runs `wt-usage` and no session key exists
- **THEN** the output shows token counts only (no percentages)
- **AND** no error is displayed

### Requirement: CLI text output formatting
The `wt-usage --format text` output SHALL be human-readable with aligned columns.

#### Scenario: Text format output
- **WHEN** user runs `wt-usage --format text`
- **THEN** the output shows token counts with thousands separators
- **AND** values are right-aligned for readability
