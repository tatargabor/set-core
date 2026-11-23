## MODIFIED Requirements

### Requirement: Standalone orchestration config file
The system SHALL support orchestration directives in `set/orchestration/config.yaml` as the primary location, with backward-compatible fallback to `.claude/orchestration.yaml`.

#### Scenario: Config file format
- **WHEN** the config file is parsed
- **THEN** it SHALL support these top-level keys (all optional):
  - `max_parallel`: integer (default: 3)
  - `merge_policy`: one of "eager", "checkpoint", "manual" (default: "checkpoint")
  - `checkpoint_every`: integer (default: 3)
  - `test_command`: string (default: empty)
  - `notification`: one of "desktop", "gui", "none" (default: "desktop")
  - `token_budget`: integer, 0 = unlimited (default: 0)
  - `design_source_path`: string or null (default: null) — absolute or ~-expandable path to external design directory

#### Scenario: Design source path directive
- **WHEN** `design_source_path` is set to a valid path like `~/projects/consumer-app-design`
- **THEN** the system SHALL expand `~` to the user's home directory
- **AND** SHALL use this path as the design source for the design pipeline
- **WHEN** `design_source_path` is null or omitted
- **THEN** the system SHALL use the existing in-project `v0-export/` detection
