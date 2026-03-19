## ADDED Requirements

### Requirement: Single unified handler script
A single script `bin/wt-hook-memory` SHALL handle all memory hook events. It SHALL accept the event name as its first argument and dispatch to event-specific logic internally.

#### Scenario: SessionStart event
- **WHEN** `wt-hook-memory SessionStart` is called
- **THEN** it SHALL perform proactive context loading using git changed files (not commit messages) as context
- **AND** SHALL clear the session dedup cache (only if source=startup or source=clear)

#### Scenario: UserPromptSubmit event
- **WHEN** `wt-hook-memory UserPromptSubmit` is called with prompt text in stdin JSON
- **THEN** it SHALL extract the prompt and recall relevant memories
- **AND** SHALL output additionalContext with label "PROJECT MEMORY — Use this context before independent research"
- **AND** SHALL NOT skip recall when memory count is zero (fresh projects still benefit from proactive context)

#### Scenario: PreToolUse event
- **WHEN** `wt-hook-memory PreToolUse` is called
- **THEN** it SHALL extract the query from tool_input (file_path, command, or prompt depending on tool)
- **AND** SHALL use `set-memory proactive` (not just recall) for richer context surfacing
- **AND** SHALL inject results as additionalContext

#### Scenario: PostToolUse event
- **WHEN** `wt-hook-memory PostToolUse` is called
- **THEN** it SHALL extract the query from tool_input and tool_output
- **AND** SHALL recall memories and inject as additionalContext
- **AND** for Edit/Write tools, SHALL create a FileAccess memory recording the modification
- **AND** for Bash tools with error-like output, SHALL store the error pattern as a Learning memory

#### Scenario: PostToolUseFailure event
- **WHEN** `wt-hook-memory PostToolUseFailure` is called
- **THEN** it SHALL extract the error text and recall past fixes
- **AND** SHALL auto-promote the failed command to hot topics (legacy behavior preserved)

#### Scenario: SubagentStop event
- **WHEN** `wt-hook-memory SubagentStop` is called
- **THEN** it SHALL read the subagent's transcript summary from `agent_transcript_path` (last few entries)
- **AND** SHALL use the summary as query for `set-memory proactive`
- **AND** SHALL inject relevant memories as additionalContext

#### Scenario: Stop event
- **WHEN** `wt-hook-memory Stop` is called
- **THEN** it SHALL perform transcript extraction and memory saving (current save behavior)
- **AND** SHALL clean up the session dedup cache file

#### Scenario: Unknown event
- **WHEN** `wt-hook-memory UnknownEvent` is called
- **THEN** it SHALL exit 0 silently

### Requirement: Shared health check
The unified handler SHALL check `set-memory health` once at the start and exit 0 if unhealthy. This avoids repeating the check in each event handler.

#### Scenario: set-memory not available
- **WHEN** `set-memory` is not in PATH
- **THEN** the handler SHALL exit 0 immediately for any event

### Requirement: Session-level deduplication cache
The handler SHALL maintain a session-scoped cache to prevent redundant recalls for the same query.

#### Scenario: Same file read twice
- **WHEN** PostToolUse fires for Read of `cnc/contour.py`
- **AND** a recall for `cnc/contour.py` was already performed in this session
- **THEN** the handler SHALL exit 0 immediately with no output

#### Scenario: Cache key generation
- **WHEN** a recall query is about to be issued
- **THEN** the cache key SHALL be derived from `event_type + tool_name + query_text` (truncated hash)

#### Scenario: Cache location
- **WHEN** the handler starts
- **THEN** the cache file SHALL be at `/tmp/set-memory-session-<SESSION_ID>.json`
- **AND** `SESSION_ID` SHALL be extracted from the `session_id` field of the hook input JSON

#### Scenario: Cache cleared on new session
- **WHEN** SessionStart event fires with `source` = `startup` or `clear`
- **THEN** any existing cache file for this session SHALL be deleted

#### Scenario: Cache preserved on resume/compact
- **WHEN** SessionStart event fires with `source` = `resume` or `compact`
- **THEN** the existing cache file SHALL be preserved (session is continuing)

### Requirement: Backward-compatible wrapper scripts
During transition, the old script names SHALL continue to work as thin wrappers.

#### Scenario: Old script name called
- **WHEN** `wt-hook-memory-recall` is called (old name)
- **THEN** it SHALL exec `wt-hook-memory UserPromptSubmit` with stdin passed through

#### Scenario: Old warmstart script called
- **WHEN** `wt-hook-memory-warmstart` is called
- **THEN** it SHALL exec `wt-hook-memory SessionStart` with stdin passed through
