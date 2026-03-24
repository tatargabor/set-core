## Requirements

### REQ-1: Scaffold branch naming
- **GIVEN** `run-complex.sh` creates a project from a spec-only branch
- **WHEN** the scaffold script completes
- **THEN** the main branch SHALL be named `main` (not `spec-only`)
- **AND** `run.sh` (minishop) SHALL also rename its branch to `main`

### REQ-2: build_broken_on_main auto-clear
- **GIVEN** `build_broken_on_main` flag is set in orchestration state
- **WHEN** the Python monitor polls (every 5th cycle, ~75s)
- **THEN** it SHALL re-run the build command on main
- **AND** clear the flag if build succeeds
- **AND** log the auto-clear event

### REQ-3: Memory project resolution
- **GIVEN** a memory hook runs inside an agent worktree session
- **WHEN** the hook resolves the project name for memory operations
- **THEN** it SHALL use `CLAUDE_PROJECT_DIR` env var if set
- **AND** fall back to git worktree common-dir resolution
- **AND** never use the caller session's project name

### REQ-4: Config template default model
- **GIVEN** `run-complex.sh` generates `set/orchestration/config.yaml`
- **WHEN** a new E2E project is scaffolded
- **THEN** config SHALL include `default_model: opus` with a comment showing `opus-1m` as alternative

### REQ-5: Python monitor heartbeat
- **GIVEN** the Python monitor runs poll cycles
- **WHEN** each poll cycle completes
- **THEN** it SHALL write a timestamped heartbeat to the orchestration log
- **AND** the bash sentinel SHALL recognize heartbeats as progress (not trigger watchdog)
