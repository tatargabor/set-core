## Requirements

### Requirement: Single unified handler script
A single script `bin/wt-hook-memory` SHALL handle all memory hook events. It SHALL accept the event name as its first argument and dispatch to event-specific logic internally. Each event handler SHALL additionally record injection metrics when metrics collection is enabled.

#### Scenario: SessionStart event
- **WHEN** `wt-hook-memory SessionStart` is called
- **THEN** it SHALL perform proactive context loading using git changed files (not commit messages) as context
- **AND** SHALL clear the session dedup cache (only if source=startup or source=clear)
- **AND** SHALL record an L1 metrics entry with timing, result counts, and relevance scores (if metrics enabled)

#### Scenario: UserPromptSubmit event
- **WHEN** `wt-hook-memory UserPromptSubmit` is called with prompt text in stdin JSON
- **THEN** it SHALL increment the session turn counter in the dedup cache
- **AND** SHALL check if the checkpoint threshold has been reached and trigger checkpoint save if so
- **AND** SHALL extract the prompt and recall relevant memories
- **AND** SHALL output additionalContext with label "PROJECT MEMORY — Use this context before independent research"
- **AND** SHALL NOT skip recall when memory count is zero (fresh projects still benefit from proactive context)
- **AND** SHALL record an L2 metrics entry with timing, result counts, relevance scores, and emotion detection result (if metrics enabled)

#### Scenario: PostToolUse event
- **WHEN** `wt-hook-memory PostToolUse` is called
- **THEN** for Bash tool with git commit command, it SHALL save the commit message as a Learning memory (commit-save)
- **AND** for Read and Bash tools, SHALL recall memories and inject as additionalContext
- **AND** SHALL record an L3 metrics entry with timing, result counts, relevance scores, and dedup hit/miss (if metrics enabled)
- **AND** for any tool not in scope (not Read or Bash), SHALL exit immediately
