## Requirements

### Requirement: PostToolUse hook surfaces memory after supported tool calls
A `PostToolUse` hook SHALL fire after successful execution of Read and Bash tools. For Read and Bash (non-commit) tools, the hook SHALL extract a query from the tool's input and recall relevant memories via `set-memory proactive`, injecting results as `additionalContext`. For Bash (git commit) tools, the hook SHALL perform commit-save logic before recall.

#### Scenario: After reading a file
- **WHEN** Claude successfully reads a file
- **THEN** the PostToolUse hook SHALL recall memories using the file path as query
- **AND** SHALL inject results using top-level `additionalContext` JSON

#### Scenario: After executing a Bash command (non-commit)
- **WHEN** Claude successfully executes a Bash command that does not contain `git commit`
- **THEN** the PostToolUse hook SHALL recall memories using the command text as query
- **AND** SHALL inject results as a system-reminder

#### Scenario: After a git commit via Bash
- **WHEN** Claude successfully executes a Bash command containing `git commit`
- **THEN** the PostToolUse hook SHALL save a commit-save memory with the commit message
- **AND** SHALL also proceed with normal Bash recall logic

#### Scenario: After a Grep or Glob search
- **WHEN** a Grep or Glob tool call completes successfully
- **THEN** the PostToolUse hook SHALL NOT fire (not in scope)

#### Scenario: After a Write or Edit tool
- **WHEN** a Write or Edit tool call completes successfully
- **THEN** the PostToolUse hook SHALL NOT fire (no matcher deployed)
