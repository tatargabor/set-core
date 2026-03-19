## ADDED Requirements

### Requirement: PostToolUse hook surfaces memory after every supported tool call
A `PostToolUse` hook SHALL fire after successful execution of Read, Edit, Write, Bash, Task, and Grep tools. The hook SHALL extract a query from the tool's input/output and recall relevant memories via `set-memory recall`, injecting results as `additionalContext`.

#### Scenario: After reading a file
- **WHEN** Claude successfully reads `moldmaker/cnc/contour.py`
- **THEN** the PostToolUse hook SHALL recall memories using the file path as query
- **AND** SHALL inject results using top-level `additionalContext` JSON (not `hookSpecificOutput`)

#### Scenario: After executing a Bash command
- **WHEN** Claude successfully executes `git diff HEAD -- moldmaker/cnc/gcode.py`
- **THEN** the PostToolUse hook SHALL recall memories using the command text as query
- **AND** SHALL inject results as a system-reminder

#### Scenario: After editing a file
- **WHEN** Claude successfully edits `bin/wt-hook-memory`
- **THEN** the PostToolUse hook SHALL recall memories using the file path as query

#### Scenario: After a Task/Explore subagent returns
- **WHEN** a Task tool call completes successfully
- **THEN** the PostToolUse hook SHALL recall memories using the task prompt as query

#### Scenario: Tool with no output (empty result)
- **WHEN** a tool call succeeds but produces no meaningful output
- **THEN** the hook SHALL still attempt recall using tool_input as the query source

### Requirement: Query extraction is tool-specific
The hook SHALL extract the most semantically meaningful query text from each tool type's input and output.

#### Scenario: Read tool query extraction
- **WHEN** PostToolUse fires for a Read tool
- **THEN** the query SHALL be the file basename plus parent directory (e.g., `"cnc/contour.py"`)

#### Scenario: Edit/Write tool query extraction
- **WHEN** PostToolUse fires for an Edit or Write tool
- **THEN** the query SHALL be the file basename plus parent directory

#### Scenario: Bash tool query extraction
- **WHEN** PostToolUse fires for a Bash tool
- **THEN** the query SHALL be the first 200 characters of the command text

#### Scenario: Task tool query extraction
- **WHEN** PostToolUse fires for a Task tool
- **THEN** the query SHALL be the first 200 characters of the task prompt

#### Scenario: Grep tool query extraction
- **WHEN** PostToolUse fires for a Grep tool
- **THEN** the query SHALL be the search pattern text

### Requirement: Memory limit per injection is 2
Each PostToolUse recall SHALL request at most 2 memories (`--limit 2`). This keeps context concise and avoids overwhelming the agent with too much background.

#### Scenario: Multiple memories available
- **WHEN** a recall returns 5 potential matches
- **THEN** only the top 2 by relevance SHALL be injected

### Requirement: Relevance threshold filtering
Memories with relevance score below 0.3 SHALL be filtered out before injection.

#### Scenario: Low-relevance memories
- **WHEN** a recall returns memories with scores [0.8, 0.2, 0.1]
- **THEN** only the memory with score 0.8 SHALL be injected

### Requirement: PostToolUse creates FileAccess memories for Edit/Write
After successful Edit or Write tool calls, the hook SHALL create a memory recording the file interaction. This builds the knowledge graph of which files the agent has modified.

#### Scenario: After editing a file
- **WHEN** PostToolUse fires for Edit of `bin/wt-hook-memory`
- **THEN** the hook SHALL call `set-memory remember --type Context --tags "file-access,<file_path>"` with a summary of the modification
- **AND** the content SHALL include the file path and a brief description extracted from tool_input (old_string → new_string summary, truncated)

#### Scenario: After writing a file
- **WHEN** PostToolUse fires for Write of `bin/set-memory-mcp-server.py`
- **THEN** the hook SHALL call `set-memory remember --type Context --tags "file-access,<file_path>"` recording the file creation

#### Scenario: Read does NOT create FileAccess
- **WHEN** PostToolUse fires for Read
- **THEN** the hook SHALL NOT create a FileAccess memory (only recall)

### Requirement: PostToolUse stores error patterns from Bash stderr
After successful Bash tool calls that contain error-like output (stderr, warnings), the hook SHALL store the error pattern as a Learning memory for future reference.

#### Scenario: Bash command with error in output
- **WHEN** PostToolUse fires for Bash
- **AND** the tool_output contains "error", "Error", "failed", "FAILED", or "warning"
- **THEN** the hook SHALL call `set-memory remember --type Learning --tags "error,bash"` with the command and error excerpt
- **AND** the content SHALL be truncated to 300 characters

#### Scenario: Bash command with clean output
- **WHEN** PostToolUse fires for Bash
- **AND** the tool_output does NOT contain error-like patterns
- **THEN** the hook SHALL NOT create a memory (only recall)
