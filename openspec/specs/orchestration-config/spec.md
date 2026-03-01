# orchestration-config Specification

## Purpose
TBD - created by archiving change spec-driven-orchestration. Update Purpose after archive.
## Requirements
### Requirement: Standalone orchestration config file
The system SHALL support a `.claude/orchestration.yaml` file for orchestrator directives, decoupled from the spec/brief document.

#### Scenario: Config file loading
- **WHEN** `.claude/orchestration.yaml` exists in the project root
- **THEN** the system SHALL parse it as YAML and extract directive values

#### Scenario: Config file format
- **WHEN** the config file is parsed
- **THEN** it SHALL support these top-level keys (all optional):
  - `max_parallel`: integer (default: 2)
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
  - `review_before_merge`: boolean (default: false) — whether to run code review in verify gate
  - `max_verify_retries`: integer (default: 1) — max retries for failed verify gate
  - `test_timeout`: integer in seconds (default: 300) — timeout for test command
  - `auto_replan`: boolean (default: false) — re-plan when all changes complete

#### Scenario: Config file absent
- **WHEN** `.claude/orchestration.yaml` does not exist
- **THEN** the system SHALL proceed without error using other sources or defaults

### Requirement: Directive precedence chain
The system SHALL resolve directive values through a precedence chain where higher sources override lower ones.

#### Scenario: Precedence order
- **WHEN** directives are resolved
- **THEN** the precedence SHALL be (highest to lowest):
  1. CLI flags (e.g., `--max-parallel 3`)
  2. `.claude/orchestration.yaml`
  3. `## Orchestrator Directives` section in the input document (brief or spec)
  4. Built-in defaults

#### Scenario: Partial override
- **WHEN** a higher-precedence source defines only some directives
- **THEN** unspecified directives SHALL fall through to the next source in the chain

### Requirement: YAML parsing robustness
The system SHALL handle YAML parsing errors gracefully.

#### Scenario: Malformed YAML
- **WHEN** `.claude/orchestration.yaml` exists but contains invalid YAML
- **THEN** the system SHALL log a warning: "Could not parse .claude/orchestration.yaml: <error>"
- **AND** continue with the next precedence source

#### Scenario: Unknown keys
- **WHEN** the config file contains unrecognized keys
- **THEN** the system SHALL log a warning for each: "Unknown directive '<key>', ignoring"
- **AND** process recognized keys normally

#### Scenario: Invalid values
- **WHEN** a directive value fails validation (e.g., `max_parallel: -1`)
- **THEN** the system SHALL log a warning and use the default for that directive

