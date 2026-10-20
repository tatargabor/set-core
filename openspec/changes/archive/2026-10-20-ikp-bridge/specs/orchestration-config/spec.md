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
  - `pause_on_exit`: boolean (default: false)
  - `default_model`: one of "opus", "sonnet", "haiku" (default: "opus") — global model for implementation work
  - `review_model`: one of "opus", "sonnet", "haiku" (default: "sonnet") — model for code review in verify gate
  - `summarize_model`: one of "opus", "sonnet", "haiku" (default: "haiku") — model for spec summarization
  - `smoke_command`: string (default: empty) — command to run as smoke test after merge
  - `smoke_timeout`: integer in seconds (default: 60) — timeout for smoke command
  - `post_merge_command`: string (default: empty) — custom command to run after dep install, before build verify (e.g., `pnpm db:generate`)
  - `review_before_merge`: boolean (default: false) — whether to run code review in verify gate
  - `max_verify_retries`: integer (default: 1) — max retries for failed verify gate
  - `test_timeout`: integer in seconds (default: 300) — timeout for test command
  - `auto_replan`: boolean (default: false) — re-plan when all changes complete
  - `token_hard_limit`: integer (default: 20000000) — cumulative token checkpoint; triggers approval prompt at each multiple
  - `ikp_pipeline`: one of "auto", "none" (default: "auto")

#### Scenario: Config file absent
- **WHEN** neither config file exists
- **THEN** the system SHALL proceed without error using other sources or defaults

#### Scenario: IKP pipeline directive
- **WHEN** `ikp_pipeline` is set to `"none"`
- **THEN** the system SHALL disable IKP integration entirely
- **WHEN** `ikp_pipeline` is set to `"auto"` or omitted
- **THEN** the system SHALL enable IKP integration if `.ikp.yaml` exists and ikp package is installed
