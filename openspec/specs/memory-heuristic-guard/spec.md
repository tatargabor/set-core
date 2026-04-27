# Memory Heuristic Guard Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Heuristic memory detection at display time
The system SHALL detect heuristic/pattern-matching language in memory content during `proactive_and_format()` and visually mark it before injection into the agent's system-reminder.

Heuristic patterns to detect (case-insensitive):
- `false positive`
- `same pattern`
- `known pattern`
- `known issue`
- `was a false`
- `unlike previous`
- `same issue as`
- `this is not a real`

#### Scenario: Memory containing heuristic language is marked
- **WHEN** a recalled memory contains the phrase "false positive" or "known pattern"
- **THEN** the injected line SHALL be prefixed with `⚠️ HEURISTIC: ` after the `[MEM#xxxx]` tag
- **AND** the memory content SHALL still be fully visible (not filtered)

#### Scenario: Memory without heuristic language is unchanged
- **WHEN** a recalled memory contains only deterministic content (e.g., "fresh worktrees need prisma generate")
- **THEN** the injected line SHALL NOT have the `⚠️ HEURISTIC` prefix

#### Scenario: Existing memories are detected retroactively
- **WHEN** an existing memory in the database contains heuristic language
- **THEN** it SHALL be marked with the `⚠️ HEURISTIC` prefix at display time without requiring a database migration

### Requirement: Volatile tag at extraction time
The system SHALL tag memories whose content matches heuristic patterns with `volatile` during stop-hook raw transcript extraction (`_stop_raw_filter()`).

#### Scenario: New heuristic memory gets volatile tag
- **WHEN** the stop hook extracts a memory from the transcript that contains "false positive" or other heuristic patterns
- **THEN** the memory SHALL be saved with the `volatile` tag appended to its tag list

#### Scenario: Non-heuristic memory is not tagged volatile
- **WHEN** the stop hook extracts a memory that contains only deterministic content
- **THEN** the memory SHALL NOT receive the `volatile` tag

### Requirement: Volatile decay in orchestration recall
The `orch_recall()` function SHALL filter out memories tagged `volatile` that are older than 24 hours.

#### Scenario: Recent volatile memory is included
- **WHEN** `orch_recall()` retrieves memories and a volatile-tagged memory was created less than 24 hours ago
- **THEN** the memory SHALL be included in the recall results

#### Scenario: Old volatile memory is excluded
- **WHEN** `orch_recall()` retrieves memories and a volatile-tagged memory was created more than 24 hours ago
- **THEN** the memory SHALL be excluded from the recall results

#### Scenario: Non-volatile memory is never affected by decay
- **WHEN** `orch_recall()` retrieves memories and a memory without the `volatile` tag was created more than 24 hours ago
- **THEN** the memory SHALL be included normally (no decay applied)

#### Scenario: Stale filter still applies
- **WHEN** a memory is tagged both `volatile` and `stale:true`
- **THEN** the memory SHALL be excluded regardless of age (existing stale filter takes precedence)
