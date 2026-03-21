## ADDED Requirements

### Requirement: Reflection injected into subsequent iteration prompt
The `build_claude_prompt()` function (loop_prompt.py:23) SHALL call `get_previous_iteration_summary(wt_path)` (loop_prompt.py:202) and inject the result into the prompt when non-empty.

#### Scenario: Previous reflection exists
- **WHEN** `build_claude_prompt()` is called for any iteration
- **AND** `get_previous_iteration_summary(wt_path)` returns non-empty content
- **THEN** the prompt SHALL include a "Previous iteration learned:\n{content}" section after the `prev_text` (commit history) and before the reflection instruction

#### Scenario: No previous reflection
- **WHEN** `get_previous_iteration_summary(wt_path)` returns empty string (file doesn't exist or is empty)
- **THEN** the prompt SHALL not include a reflection section

### Requirement: Reflection saved to persistent memory
After the agent iteration loop completes in cli.py (~line 943, where `build_claude_prompt` is called), the system SHALL save non-trivial reflections to persistent memory.

#### Scenario: Meaningful reflection
- **WHEN** an agent iteration completes and `.claude/reflection.md` exists in the worktree
- **AND** the content is longer than 50 characters and does not match "No notable issues."
- **THEN** `orch_remember(content, mem_type="Learning", tags=f"change:{target_change}")` SHALL be called

#### Scenario: Trivial reflection
- **WHEN** `.claude/reflection.md` contains only "No notable issues." or is fewer than 50 characters
- **THEN** `orch_remember()` SHALL NOT be called
