## MODIFIED Requirements

### Requirement: Detection bridge skips malformed findings
The `DetectionBridge` SHALL skip any finding that is missing a non-empty `summary` or a non-empty `severity`, and SHALL log a WARNING that names the project and finding id so operators can investigate the sentinel data.

#### Scenario: Finding without summary is skipped
- **WHEN** `DetectionBridge._scan_project()` encounters a finding where `summary` is absent or empty string
- **THEN** the finding SHALL NOT be passed to `issue_manager.register()`
- **AND** a WARNING log line SHALL be emitted: `"Skipping malformed finding %s in %s: missing summary"`

#### Scenario: Finding without severity is skipped
- **WHEN** `DetectionBridge._scan_project()` encounters a finding where `severity` is absent or empty string
- **THEN** the finding SHALL NOT be passed to `issue_manager.register()`
- **AND** a WARNING log line SHALL be emitted: `"Skipping malformed finding %s in %s: missing severity"`

#### Scenario: Finding with summary and severity is processed normally
- **WHEN** `DetectionBridge._scan_project()` encounters a finding with non-empty `summary` and non-empty `severity`
- **THEN** the finding SHALL be processed exactly as before (no change to registration logic)
- **AND** missing optional fields (`change`, `detail`, `discovered_at`) SHALL NOT prevent registration
