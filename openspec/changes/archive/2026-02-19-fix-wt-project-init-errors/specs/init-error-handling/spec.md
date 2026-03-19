## ADDED Requirements

### Requirement: MCP registration errors are reported
When `claude mcp add` fails during `_register_mcp_server`, the function SHALL print a warning message containing the target path and the error output from the command. The function SHALL NOT print a success message on failure.

#### Scenario: claude mcp add fails
- **WHEN** `claude mcp add set-core ...` returns a non-zero exit code
- **THEN** `_register_mcp_server` prints a warning with the failed path and error message, and returns exit code 1

#### Scenario: claude mcp add succeeds
- **WHEN** `claude mcp add set-core ...` returns exit code 0
- **THEN** `_register_mcp_server` prints the success message as before

#### Scenario: claude CLI not installed
- **WHEN** `claude` command is not found
- **THEN** `_register_mcp_server` returns 0 silently (existing behavior, unchanged)

### Requirement: MCP removal stderr is suppressed
When removing a previously registered MCP server (`claude mcp remove`), stderr SHALL be suppressed because the server may not exist. This is expected and not an error.

#### Scenario: removing non-existent server
- **WHEN** `claude mcp remove set-memory` is called and the server doesn't exist
- **THEN** stderr is suppressed and no error is shown (existing behavior, preserved)

### Requirement: deploy_set_tools tracks step failures
`deploy_set_tools` SHALL track whether any deployment step failed and return a non-zero exit code if any step produced a warning.

#### Scenario: all steps succeed
- **WHEN** hooks, commands, skills, cleanup, and MCP registration all succeed
- **THEN** `deploy_set_tools` returns 0

#### Scenario: MCP registration fails but other steps succeed
- **WHEN** MCP registration fails but hooks/commands/skills succeed
- **THEN** `deploy_set_tools` returns 1 (indicating warnings occurred)

### Requirement: cmd_init reports deployment summary
`cmd_init` SHALL report the overall deployment result after `deploy_set_tools` completes: either "complete" or "complete with warnings — check output above".

#### Scenario: deployment with warnings
- **WHEN** `deploy_set_tools` returns non-zero
- **THEN** `cmd_init` prints a warning: "set-core deployment complete for '<name>' (with warnings — check output above)"

#### Scenario: clean deployment
- **WHEN** `deploy_set_tools` returns 0
- **THEN** `cmd_init` prints success: "set-core deployment complete for '<name>'"

### Requirement: cleanup step failures are warned not swallowed
When `_cleanup_deprecated_memory_refs` encounters a python3 failure during file cleanup, it SHALL print a warning with the affected file path instead of silently continuing.

#### Scenario: python3 regex cleanup fails on a file
- **WHEN** python3 inline script fails to process a SKILL.md file
- **THEN** a warning is printed identifying the file that failed to clean up

#### Scenario: python3 regex cleanup succeeds
- **WHEN** python3 inline script successfully processes files
- **THEN** no extra output is produced (existing behavior)

### Requirement: hook deployment exit code is checked
`deploy_set_tools` SHALL check the exit code of `wt-deploy-hooks` and print a warning if it fails, instead of unconditionally printing success.

#### Scenario: wt-deploy-hooks fails
- **WHEN** `wt-deploy-hooks --quiet` returns non-zero
- **THEN** a warning is printed: "Failed to deploy hooks" and the step is counted as a warning

#### Scenario: wt-deploy-hooks succeeds
- **WHEN** `wt-deploy-hooks --quiet` returns 0
- **THEN** success message "Deployed hooks to .claude/settings.json" is printed
