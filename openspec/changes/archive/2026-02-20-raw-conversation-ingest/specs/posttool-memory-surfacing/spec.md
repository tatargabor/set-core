## MODIFIED Requirements

### Requirement: PostToolUse hook surfaces memory after supported tool calls
A `PostToolUse` hook SHALL fire after successful execution of Read and Bash tools only. The hook SHALL extract a query from the tool's input and recall relevant memories via `set-memory proactive`, injecting results as `additionalContext`.

#### Scenario: After reading a file
- **WHEN** Claude successfully reads `moldmaker/cnc/contour.py`
- **THEN** the PostToolUse hook SHALL recall memories using the file path as query
- **AND** SHALL inject results using top-level `additionalContext` JSON

#### Scenario: After executing a Bash command
- **WHEN** Claude successfully executes `git diff HEAD -- moldmaker/cnc/gcode.py`
- **THEN** the PostToolUse hook SHALL recall memories using the command text as query
- **AND** SHALL inject results as a system-reminder

#### Scenario: After editing a file
- **WHEN** Claude successfully edits `bin/wt-hook-memory`
- **THEN** the PostToolUse hook SHALL NOT fire (Edit not in scope)

#### Scenario: After writing a file
- **WHEN** Claude successfully writes a new file
- **THEN** the PostToolUse hook SHALL NOT fire (Write not in scope)

#### Scenario: After a Task/Explore subagent returns
- **WHEN** a Task tool call completes successfully
- **THEN** the PostToolUse hook SHALL NOT fire (Task not in scope)

#### Scenario: After a Grep search
- **WHEN** a Grep tool call completes successfully
- **THEN** the PostToolUse hook SHALL NOT fire (Grep not in scope)

### Requirement: Query extraction is tool-specific
The hook SHALL extract the most semantically meaningful query text from each supported tool type's input.

#### Scenario: Read tool query extraction
- **WHEN** PostToolUse fires for a Read tool
- **THEN** the query SHALL be the file basename plus parent directory (e.g., `"cnc/contour.py"`)

#### Scenario: Bash tool query extraction
- **WHEN** PostToolUse fires for a Bash tool
- **THEN** the query SHALL be the first 200 characters of the command text

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

## REMOVED Requirements

### Requirement: PostToolUse creates FileAccess memories for Edit/Write
**Reason**: "Modified FILE" memories are noise — git diff provides the same information. These memories pollute recall results without adding value.
**Migration**: No migration needed. Existing FileAccess memories remain in the database but no new ones are created.

### Requirement: PostToolUse stores error patterns from Bash stderr
**Reason**: Error patterns are better captured by the raw transcript filter at session end (full context preserved) and by PostToolUseFailure (immediate recall of past fixes). The PostToolUse error save was redundant.
**Migration**: No migration needed. PostToolUseFailure continues to handle error recall.
