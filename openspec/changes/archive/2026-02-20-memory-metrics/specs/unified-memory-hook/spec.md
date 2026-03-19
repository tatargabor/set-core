## MODIFIED Requirements

### Requirement: Single unified handler script
A single script `bin/wt-hook-memory` SHALL handle all memory hook events. It SHALL accept the event name as its first argument and dispatch to event-specific logic internally. Each event handler SHALL additionally record injection metrics when metrics collection is enabled.

#### Scenario: SessionStart event
- **WHEN** `wt-hook-memory SessionStart` is called
- **THEN** it SHALL perform proactive context loading using git changed files (not commit messages) as context
- **AND** SHALL clear the session dedup cache (only if source=startup or source=clear)
- **AND** SHALL record an L1 metrics entry with timing, result counts, and relevance scores (if metrics enabled)

#### Scenario: UserPromptSubmit event
- **WHEN** `wt-hook-memory UserPromptSubmit` is called with prompt text in stdin JSON
- **THEN** it SHALL extract the prompt and recall relevant memories
- **AND** SHALL output additionalContext with label "PROJECT MEMORY — Use this context before independent research"
- **AND** SHALL NOT skip recall when memory count is zero (fresh projects still benefit from proactive context)
- **AND** SHALL record an L2 metrics entry with timing, result counts, relevance scores, and emotion detection result (if metrics enabled)

#### Scenario: PreToolUse event
- **WHEN** `wt-hook-memory PreToolUse` is called
- **THEN** it SHALL extract the query from tool_input (file_path, command, or prompt depending on tool)
- **AND** SHALL use `set-memory proactive` (not just recall) for richer context surfacing
- **AND** SHALL inject results as additionalContext
- **AND** SHALL record an L3 metrics entry with timing, result counts, relevance scores, and dedup hit/miss (if metrics enabled)

#### Scenario: PostToolUse event
- **WHEN** `wt-hook-memory PostToolUse` is called
- **THEN** it SHALL extract the query from tool_input and tool_output
- **AND** SHALL recall memories and inject as additionalContext
- **AND** for Edit/Write tools, SHALL create a FileAccess memory recording the modification
- **AND** for Bash tools with error-like output, SHALL store the error pattern as a Learning memory
- **AND** SHALL record an L3 metrics entry (if metrics enabled)

#### Scenario: PostToolUseFailure event
- **WHEN** `wt-hook-memory PostToolUseFailure` is called
- **THEN** it SHALL extract the error text and recall past fixes
- **AND** SHALL auto-promote the failed command to hot topics (legacy behavior preserved)
- **AND** SHALL record an L4 metrics entry with timing, result counts, and relevance scores (if metrics enabled)

#### Scenario: Stop event
- **WHEN** `wt-hook-memory Stop` is called
- **THEN** it SHALL perform transcript extraction and memory saving (current save behavior)
- **AND** SHALL clean up the session dedup cache file
- **AND** SHALL flush session metrics to SQLite and run citation scanning (if metrics enabled)

#### Scenario: Unknown event
- **WHEN** `wt-hook-memory UnknownEvent` is called
- **THEN** it SHALL exit 0 silently

### Requirement: Session-level deduplication cache
The handler SHALL maintain a session-scoped cache to prevent redundant recalls for the same query. The cache file SHALL also store the `_metrics` array when metrics collection is enabled.

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
