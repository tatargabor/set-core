## Purpose
Subprocess wrappers for claude CLI, git, and general commands with logging and timeout support.

## Requirements

### Requirement: Claude CLI wrapper
The system SHALL provide a `run_claude()` function that wraps Claude CLI invocations with logging, timeout, and structured result capture.

#### Scenario: Successful Claude invocation
- **WHEN** `run_claude(prompt="...", timeout=300, model="sonnet")` is called
- **THEN** the function executes `claude -p --model sonnet` with the prompt on stdin
- **AND** returns a `ClaudeResult` dataclass with `exit_code`, `stdout`, `stderr`, `duration_ms`, `timed_out`
- **AND** logs the invocation: prompt_size, timeout, model, duration_ms, exit_code, output_size

#### Scenario: Claude timeout
- **WHEN** the Claude process exceeds the timeout
- **THEN** the process is terminated with SIGTERM
- **AND** `ClaudeResult.timed_out` is `True`
- **AND** partial stdout/stderr is captured

#### Scenario: Claude with additional flags
- **WHEN** `run_claude(prompt="...", extra_args=["--max-turns", "3", "--output-format", "stream-json"])` is called
- **THEN** the extra_args are appended to the claude command

### Requirement: Git command wrapper
The system SHALL provide a `run_git()` function that wraps git CLI invocations.

#### Scenario: Successful git command
- **WHEN** `run_git("log", "--oneline", "-5")` is called
- **THEN** the function executes `git log --oneline -5`
- **AND** returns a `GitResult` dataclass with `exit_code`, `stdout`, `stderr`, `duration_ms`
- **AND** logs the invocation at DEBUG level

#### Scenario: Git command failure
- **WHEN** the git command exits with non-zero code
- **THEN** `GitResult.exit_code` reflects the actual exit code
- **AND** the failure is logged at WARNING level

### Requirement: Generic subprocess wrapper
The system SHALL provide a `run_command()` function for arbitrary subprocess execution with timeout support.

#### Scenario: Command with timeout
- **WHEN** `run_command(["npm", "test"], timeout=120, cwd="/path")` is called
- **THEN** the command is executed in the specified working directory
- **AND** returns a `CommandResult` dataclass with `exit_code`, `stdout`, `stderr`, `duration_ms`, `timed_out`
- **AND** output is captured with configurable max_output_size (default 1MB)

#### Scenario: Output truncation
- **WHEN** command output exceeds `max_output_size`
- **THEN** output is truncated from the beginning, keeping the tail
- **AND** a truncation marker is prepended: `[...truncated, showing last N bytes...]`

### Requirement: All subprocess calls logged
Every subprocess invocation SHALL be logged with: command, duration_ms, exit_code, output_size.

#### Scenario: Logging format
- **WHEN** any subprocess wrapper completes
- **THEN** an INFO-level log is emitted with structured extras: `{"cmd": "...", "duration_ms": N, "exit_code": N, "output_size": N}`
