## ADDED Requirements

### Requirement: Background Chrome session scanning
The system SHALL perform Chrome session scanning on a background QThread, never blocking the GUI main thread.

#### Scenario: Auto-scan on startup
- **WHEN** the Control Center starts and pycookiecheat is available
- **THEN** a `ChromeScanWorker` thread SHALL be started after a 2-second delay
- **AND** the GUI SHALL remain responsive during the scan
- **AND** results SHALL be delivered via a Qt signal to the main thread

#### Scenario: Manual scan from menu
- **WHEN** the user triggers "Scan Chrome Sessions" from the menu
- **THEN** a `ChromeScanWorker` thread SHALL be started
- **AND** the GUI SHALL remain responsive during the scan
- **AND** a result dialog SHALL be shown when the scan completes

#### Scenario: Scan error handling
- **WHEN** the background scan encounters an error
- **THEN** the error SHALL be emitted via a `scan_error` signal
- **AND** the GUI SHALL log the error (auto-scan) or show a warning dialog (manual scan)
- **AND** the GUI SHALL NOT crash or freeze

#### Scenario: Concurrent scan prevention
- **WHEN** a scan is already running
- **AND** another scan is requested
- **THEN** the second request SHALL be ignored
- **AND** a debug log message SHALL indicate a scan is already in progress

### Requirement: Org name caching
The scanner SHALL cache org names to avoid redundant API calls on repeat scans.

#### Scenario: First scan discovers org name
- **WHEN** a Chrome profile has a valid sessionKey
- **AND** no cached org name exists for that sessionKey
- **THEN** the scanner SHALL fetch the org name from the Claude API
- **AND** store it in the account entry as `org_name`

#### Scenario: Subsequent auto-scan uses cached org name
- **WHEN** auto-scan runs and an account entry has a cached `org_name`
- **AND** the `sessionKey` has not changed
- **THEN** the scanner SHALL use the cached org name without an API call

#### Scenario: Manual scan re-fetches org names
- **WHEN** the user triggers a manual scan
- **THEN** the scanner SHALL re-fetch org names from the API for all discovered sessions
- **AND** update the cached `org_name` values

#### Scenario: Session key changed invalidates cache
- **WHEN** auto-scan detects a sessionKey that differs from the cached entry
- **THEN** the cached `org_name` SHALL be discarded
- **AND** the org name SHALL be re-fetched from the API
