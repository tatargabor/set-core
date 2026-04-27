# Session Warmstart Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: SessionStart hook loads operational cheat sheet
A new hook script `set-hook-memory-warmstart` SHALL run on the `SessionStart` event and load memories tagged `cheat-sheet` from set-memory into Claude's context via `additionalContext`.

#### Scenario: Session starts with cheat-sheet memories available
- **WHEN** a Claude Code session starts
- **AND** set-memory is healthy
- **AND** memories tagged `cheat-sheet` exist for the current project
- **THEN** the hook SHALL recall memories with tag filter `cheat-sheet`
- **AND** SHALL output JSON with `hookSpecificOutput.additionalContext` containing the formatted memories
- **AND** the output SHALL be prefixed with `=== OPERATIONAL CHEAT SHEET ===`

#### Scenario: Session starts with no cheat-sheet memories
- **WHEN** a Claude Code session starts
- **AND** set-memory is healthy
- **AND** no memories tagged `cheat-sheet` exist
- **THEN** the hook SHALL exit 0 silently with no output

#### Scenario: set-memory not available
- **WHEN** a Claude Code session starts
- **AND** `set-memory health` fails or set-memory is not installed
- **THEN** the hook SHALL exit 0 silently with no output

### Requirement: Hot-topic discovery at session start
The SessionStart hook SHALL discover project-specific hot topics by scanning project structure and memory tags, and write the results to `.claude/hot-topics.json` for L3 (PreToolUse) to consume. See `hot-topic-recall` spec for discovery sources and cache format.

#### Scenario: First session in a project
- **WHEN** a session starts and `.claude/hot-topics.json` does not exist
- **THEN** the hook SHALL run discovery and create the cache file

#### Scenario: Subsequent sessions
- **WHEN** a session starts and `.claude/hot-topics.json` already exists
- **THEN** the hook SHALL regenerate the cache (discovery is fast, always refresh)

### Requirement: Cheat sheet includes project context
The SessionStart hook SHALL also run `set-memory proactive` with the project name and recent git activity as context, appending relevant non-cheat-sheet memories separately.

#### Scenario: Project has recent git activity
- **WHEN** a session starts in a git repository
- **AND** set-memory proactive returns relevant memories
- **THEN** the hook SHALL include proactive memories in a `=== PROJECT CONTEXT ===` section after the cheat sheet
- **AND** SHALL limit to 5 proactive memories

#### Scenario: Project has no git history
- **WHEN** a session starts in a non-git directory
- **THEN** the hook SHALL skip proactive context and only load cheat-sheet memories

### Requirement: SessionStart hook timeout
The SessionStart hook SHALL complete within 10 seconds.

#### Scenario: set-memory recall is slow
- **WHEN** set-memory recall takes longer than 8 seconds
- **THEN** the hook SHALL return whatever results it has so far
- **AND** SHALL NOT exceed the 10-second timeout

### Requirement: Hook deployment includes SessionStart
The `set-deploy-hooks` script SHALL include `set-hook-memory-warmstart` in the `SessionStart` hook event.

#### Scenario: Deploy adds SessionStart hook
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **THEN** settings.json SHALL contain a `SessionStart` entry with `set-hook-memory-warmstart`
- **AND** the timeout SHALL be 10 seconds
