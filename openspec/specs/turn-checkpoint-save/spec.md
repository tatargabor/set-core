# Turn Checkpoint Save Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Turn counter in session dedup cache
The `handle_user_prompt()` function SHALL increment a `turn_count` integer in the session dedup cache on every UserPromptSubmit event. The counter SHALL start at 1 on the first prompt of the session.

#### Scenario: First prompt in session
- **WHEN** `set-hook-memory UserPromptSubmit` is called and no `turn_count` exists in cache
- **THEN** `turn_count` SHALL be set to 1 in the cache file

#### Scenario: Subsequent prompts
- **WHEN** `set-hook-memory UserPromptSubmit` is called and `turn_count` is N in cache
- **THEN** `turn_count` SHALL be updated to N+1

### Requirement: Checkpoint trigger at configurable interval
When `turn_count - last_checkpoint_turn >= CHECKPOINT_INTERVAL` (default: 15), the handler SHALL trigger a checkpoint save before proceeding with normal recall logic. The `last_checkpoint_turn` SHALL be updated to the current `turn_count` after a successful checkpoint.

#### Scenario: Checkpoint threshold reached
- **WHEN** `turn_count` is 15 and `last_checkpoint_turn` is 0
- **THEN** a checkpoint save SHALL execute
- **AND** `last_checkpoint_turn` SHALL be updated to 15

#### Scenario: Below threshold
- **WHEN** `turn_count` is 10 and `last_checkpoint_turn` is 0
- **THEN** no checkpoint save SHALL execute

#### Scenario: Second checkpoint
- **WHEN** `turn_count` is 30 and `last_checkpoint_turn` is 15
- **THEN** a checkpoint save SHALL execute
- **AND** `last_checkpoint_turn` SHALL be updated to 30

### Requirement: Checkpoint save content from metrics summary
The checkpoint save SHALL summarize accumulated `_metrics` entries since `last_checkpoint_turn` into a single Context memory. The summary SHALL include: turn range, files read (unique file paths from Read tool queries), commands run (count of Bash entries), and topic keywords (extracted from UserPromptSubmit queries).

#### Scenario: Checkpoint with mixed activity
- **WHEN** checkpoint fires at turn 15
- **AND** metrics since turn 0 contain 5 Read events, 3 Bash events, and prompts about "memory hooks" and "GUI testing"
- **THEN** the saved memory SHALL contain: `[session checkpoint, turns 1-15] Files: bin/set-hook-memory, gui/main.py, ... | Commands: 3 | Topics: memory hooks, GUI testing`
- **AND** the memory type SHALL be Context
- **AND** tags SHALL include `phase:checkpoint,source:hook`

#### Scenario: Checkpoint with no tool activity
- **WHEN** checkpoint fires at turn 15
- **AND** metrics since turn 0 contain only UserPromptSubmit entries (no tool use)
- **THEN** the saved memory SHALL contain only topics from prompts
- **AND** SHALL still save (conversation-only sessions are worth recording)

### Requirement: Checkpoint entries pruned after save
After a successful checkpoint save, the `_metrics` entries used for the summary SHALL NOT be deleted (they are still needed for Stop hook flush). Only the `last_checkpoint_turn` marker SHALL be updated.

#### Scenario: Metrics preserved after checkpoint
- **WHEN** checkpoint fires and saves successfully
- **THEN** the `_metrics` array SHALL remain intact
- **AND** only `last_checkpoint_turn` SHALL be updated in the cache
