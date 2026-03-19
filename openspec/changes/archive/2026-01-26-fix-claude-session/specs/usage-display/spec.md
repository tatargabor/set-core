# usage-display Spec Delta

## MODIFIED Requirements

### Requirement: Display Claude Capacity Statistics
The Control Center GUI SHALL display Claude Code capacity statistics via progress bars.

#### Scenario: Capacity from local JSONL files (primary)
- **GIVEN** Claude Code has been used and JSONL files exist in `~/.claude/projects/`
- **WHEN** the usage worker runs
- **THEN** it parses local JSONL files for token usage
- **AND** calculates 5h and 7-day window usage from timestamps
- **AND** estimates percentage based on configurable limits
- **AND** displays with "~" prefix to indicate estimated values

#### Scenario: Capacity from claude.ai API (secondary)
- **GIVEN** the user has logged in via WebView
- **AND** a valid session key is stored
- **WHEN** the usage worker runs
- **THEN** it fetches exact usage from claude.ai API
- **AND** displays without "~" prefix (exact values)

#### Scenario: No local data available
- **GIVEN** no JSONL files exist in `~/.claude/projects/`
- **AND** no session key is stored
- **WHEN** the usage worker runs
- **THEN** it displays "N/A" with "Login for data" link

### Requirement: Background Usage Data Fetching
Usage data SHALL be fetched periodically in a background thread to avoid blocking the UI.

#### Scenario: Local JSONL parsing
- **GIVEN** the Control Center is running
- **WHEN** 30 seconds have elapsed since the last fetch
- **THEN** the usage worker parses local JSONL files
- **AND** updates the progress bars

#### Scenario: Fallback to API when logged in
- **GIVEN** the user has a valid session
- **WHEN** local parsing completes
- **THEN** the worker also fetches API data for accuracy
- **AND** uses API data if available, local data otherwise

## ADDED Requirements

### Requirement: Cross-Platform File Access
The usage calculator SHALL work on Linux, macOS, and Windows.

#### Scenario: Find Claude data directory on Linux
- **GIVEN** the user runs set-core on Linux
- **WHEN** the usage calculator initializes
- **THEN** it locates `~/.claude/projects/`
- **AND** uses forward slashes for paths

#### Scenario: Find Claude data directory on macOS
- **GIVEN** the user runs set-core on macOS
- **WHEN** the usage calculator initializes
- **THEN** it locates `~/.claude/projects/`
- **AND** uses forward slashes for paths

#### Scenario: Find Claude data directory on Windows
- **GIVEN** the user runs set-core on Windows
- **WHEN** the usage calculator initializes
- **THEN** it locates `%USERPROFILE%\.claude\projects\`
- **AND** handles both forward and back slashes

#### Scenario: Parse JSONL token data
- **GIVEN** JSONL files exist with message data
- **WHEN** the calculator parses a file
- **THEN** it extracts `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`
- **AND** uses the `timestamp` field for time window filtering

#### Scenario: Handle malformed JSONL lines
- **GIVEN** a JSONL file contains invalid JSON lines
- **WHEN** the calculator parses the file
- **THEN** it skips invalid lines without crashing
- **AND** logs a warning for debugging

### Requirement: Configurable Usage Limits
Users SHALL be able to configure estimated usage limits for their subscription tier.

#### Scenario: Default limits
- **GIVEN** no custom limits are configured
- **WHEN** usage percentage is calculated
- **THEN** default limits are used (500k tokens/5h, 5M tokens/week)

#### Scenario: Custom limits
- **GIVEN** the user has configured custom limits in settings
- **WHEN** usage percentage is calculated
- **THEN** the custom limits are used for percentage calculation

#### Scenario: Settings UI for limits
- **GIVEN** the settings dialog is open
- **WHEN** the user views the "Usage" tab
- **THEN** spinboxes for 5h and weekly token limits are shown
- **AND** changes are saved to config

### Requirement: Usage Calculator Testing
The usage calculator SHALL have automated tests.

#### Scenario: Unit test JSONL parsing
- **GIVEN** a sample JSONL file with known token counts
- **WHEN** pytest runs `test_usage_calculator.py`
- **THEN** the parsed token counts match expected values

#### Scenario: Unit test time window filtering
- **GIVEN** JSONL data spanning multiple days
- **WHEN** the calculator filters for 5h window
- **THEN** only messages from last 5 hours are included

#### Scenario: Unit test percentage calculation
- **GIVEN** known token usage and limits
- **WHEN** percentage is calculated
- **THEN** the result matches expected percentage

## REMOVED Requirements

### Requirement: Browser Cookie Extraction
~~The usage worker SHALL attempt to read session cookies from browser storage.~~

**Reason**: Unreliable, platform-dependent, and not appropriate for open-source software. Replaced with local JSONL parsing (same approach as ccusage and other established tools).
