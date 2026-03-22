# memory-dedup Delta Spec

## ADDED Requirements

### Requirement: Dedup process timeout prevents orphan processes

The dedup command SHALL enforce a maximum execution timeout at the bash level. When the timeout is exceeded, the command SHALL kill the entire process tree (including grandchild Python processes) and return a timeout error in JSON format (`{"error": "timeout", "deleted_count": 0}`).

#### Scenario: Dedup times out on large memory store
- **WHEN** `set-memory dedup` runs and the Python computation exceeds 25 seconds
- **THEN** the process is killed (including all child processes) and the command returns `{"error": "timeout", "deleted_count": 0}` with exit code 0

#### Scenario: Audit times out on large memory store
- **WHEN** `set-memory audit` runs and the Python computation exceeds 25 seconds
- **THEN** the process is killed (including all child processes) and the command returns a timeout indicator with exit code 0

#### Scenario: No orphan process after caller timeout
- **WHEN** an MCP tool or orchestration function calls `set-memory dedup` and the subprocess timeout fires
- **THEN** no python3 grandchild process remains running after the caller returns

### Requirement: MCP subprocess cleanup kills process groups

The `_run_memory()` function in the MCP server SHALL spawn subprocesses in their own process group (`start_new_session=True`). On timeout, it SHALL kill the entire process group (`os.killpg`) before returning an error.

#### Scenario: MCP dedup timeout kills all children
- **WHEN** the MCP `dedup()` tool is called and the subprocess exceeds the timeout
- **THEN** the entire process group (bash + python grandchild) is terminated and no orphan processes remain

#### Scenario: Normal MCP calls unaffected
- **WHEN** the MCP `dedup()` tool completes within the timeout
- **THEN** behavior is identical to before (same JSON output, same exit code)
