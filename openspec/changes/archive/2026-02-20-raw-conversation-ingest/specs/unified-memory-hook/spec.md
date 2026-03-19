## MODIFIED Requirements

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
- **THEN** it SHALL exit 0 immediately with no output
- **AND** SHALL NOT perform any memory recall or proactive context

#### Scenario: PostToolUse event
- **WHEN** `wt-hook-memory PostToolUse` is called for a Read or Bash tool
- **THEN** it SHALL extract the query from tool_input
- **AND** SHALL recall memories and inject as additionalContext
- **AND** SHALL NOT create FileAccess memories for any tool
- **AND** SHALL NOT store error patterns from Bash output

#### Scenario: PostToolUse for non-Read/Bash tools
- **WHEN** `wt-hook-memory PostToolUse` is called for Edit, Write, Task, or Grep
- **THEN** it SHALL exit 0 immediately with no output

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
- **THEN** it SHALL launch raw transcript filter as background process
- **AND** SHALL commit any remaining staged files from previous Haiku-based sessions (one-time migration)
- **AND** SHALL clean up the session dedup cache file

#### Scenario: Unknown event
- **WHEN** `wt-hook-memory UnknownEvent` is called
- **THEN** it SHALL exit 0 silently
