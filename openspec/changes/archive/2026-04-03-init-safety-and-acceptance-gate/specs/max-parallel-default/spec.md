## MODIFIED Requirements

### Requirement: Default max_parallel is 1
The orchestrator SHALL use 1 as the default max_parallel value instead of 3. This ensures sequential execution where each change builds on the latest main, preventing cross-change integration gaps.

#### Scenario: No explicit max_parallel configured
- **WHEN** no `--max-parallel` CLI flag and no `max_parallel` directive in orchestration.yaml
- **THEN** the orchestrator SHALL dispatch at most 1 change at a time

#### Scenario: Explicit override still works
- **WHEN** `--max-parallel 3` is passed on CLI or set in orchestration.yaml
- **THEN** the orchestrator SHALL use 3, ignoring the default

#### Scenario: Template config reflects new default
- **WHEN** a new project is initialized with `set-project init --project-type web --template nextjs`
- **THEN** the deployed `set/orchestration/config.yaml` SHALL contain `max_parallel: 1`
