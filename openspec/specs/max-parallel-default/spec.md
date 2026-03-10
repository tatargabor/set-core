## ADDED Requirements

### Requirement: Default max_parallel is 3
The orchestrator SHALL use 3 as the default max_parallel value instead of 2.

#### Scenario: No explicit max_parallel configured
- **WHEN** no `--max-parallel` CLI flag and no `max_parallel` directive in orchestration.yaml
- **THEN** the orchestrator SHALL dispatch up to 3 changes concurrently

#### Scenario: Explicit override still works
- **WHEN** `--max-parallel 2` is passed on CLI
- **THEN** the orchestrator SHALL use 2, ignoring the default
