## MODIFIED Requirements

### Requirement: Standalone orchestration config file
The system SHALL support orchestration directives in `set/orchestration/config.yaml` as the primary location, with backward-compatible fallback to `.claude/orchestration.yaml`.

#### Scenario: New location config loading
- **WHEN** `set/orchestration/config.yaml` exists in the project root
- **THEN** the system SHALL parse it as YAML and extract directive values

#### Scenario: Fallback to legacy location
- **WHEN** `set/orchestration/config.yaml` does not exist
- **AND** `.claude/orchestration.yaml` exists
- **THEN** the system SHALL use `.claude/orchestration.yaml`

#### Scenario: New location takes precedence
- **WHEN** both `set/orchestration/config.yaml` and `.claude/orchestration.yaml` exist
- **THEN** the system SHALL use `set/orchestration/config.yaml`

#### Scenario: Config file format
- **WHEN** the config file is parsed
- **THEN** it SHALL support these top-level keys (all optional):
  - `max_parallel`: integer (default: 3)
  - `merge_policy`: one of "eager", "checkpoint", "manual" (default: "checkpoint")
  - `checkpoint_every`: integer (default: 3)
  - `test_command`: string (default: empty)
  - `notification`: one of "desktop", "gui", "none" (default: "desktop")
  - `token_budget`: integer, 0 = unlimited (default: 0)
  - `ikp_pipeline`: one of "auto", "none" (default: "auto")

#### Scenario: IKP pipeline directive
- **WHEN** `ikp_pipeline` is set to `"none"`
- **THEN** the system SHALL disable IKP integration entirely
- **WHEN** `ikp_pipeline` is set to `"auto"` or omitted
- **THEN** the system SHALL enable IKP integration if `.ikp.yaml` exists and ikp package is installed
