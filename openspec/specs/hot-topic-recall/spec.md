# Hot Topic Recall Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: PreToolUse hook for hot-topic Bash commands
A new hook script `set-hook-memory-pretool` SHALL run on `PreToolUse` events matching the `Bash` tool. It SHALL parse the command for hot-topic patterns (generic base + project-discovered) and inject relevant memories via `additionalContext` before the command executes.

#### Scenario: Bash command matches a discovered project hot topic
- **WHEN** Claude is about to execute a Bash command matching a pattern from `.claude/hot-topics.json`
- **AND** set-memory is healthy
- **THEN** the hook SHALL recall memories using the matched command as query
- **AND** SHALL output JSON with `hookSpecificOutput.additionalContext` containing relevant memories
- **AND** SHALL limit to 2 memories maximum

#### Scenario: Bash command matches a generic base pattern
- **WHEN** Claude is about to execute a Bash command matching a generic base pattern (ssh, rm -rf, sudo, docker/kubectl)
- **AND** set-memory is healthy
- **THEN** the hook SHALL recall memories related to that command category

#### Scenario: Bash command does not match any hot topic
- **WHEN** Claude is about to execute a Bash command that does not match any pattern (discovered or generic)
- **THEN** the hook SHALL exit 0 immediately with no output
- **AND** the total execution time SHALL be less than 5ms

### Requirement: Hot-topic pattern matching is fast
The pattern check against the command string SHALL use a single compiled regex (combining generic base + discovered patterns) and complete in under 5ms. Memory recall only executes after a positive pattern match.

#### Scenario: Non-matching command latency
- **WHEN** a Bash command like `ls -la` or `git status` is about to execute
- **THEN** the hook SHALL complete in under 5ms with no output

#### Scenario: Matching command latency
- **WHEN** a Bash command matching a hot topic is about to execute
- **THEN** the hook SHALL complete in under 5 seconds (including recall)
- **AND** typical completion time SHALL be under 500ms

### Requirement: Project-specific hot-topic discovery
The SessionStart hook (L1) SHALL discover project-specific hot topics and write them to `.claude/hot-topics.json`. Discovery sources:
1. `bin/*` scripts → extract command name prefixes
2. `package.json` scripts → npm/bun run targets
3. `Makefile` / `pyproject.toml` → project-specific commands
4. Frequently-used memory tags → topics from past sessions
5. Error memories → tools/commands that failed before

#### Scenario: set-core project discovery
- **WHEN** SessionStart runs in the set-core project
- **THEN** `.claude/hot-topics.json` SHALL contain patterns for `set-\w+`, `openspec\s`, and other project-specific commands

#### Scenario: Discovery cap
- **WHEN** discovery finds more than 20 patterns
- **THEN** the cache SHALL contain at most 20 patterns, prioritized by frequency/relevance

#### Scenario: Cache file format
- **WHEN** `.claude/hot-topics.json` is written
- **THEN** it SHALL contain `{"patterns": [...], "generated_at": "<ISO timestamp>"}`

### Requirement: Generic base patterns are always active
Regardless of discovery, the following base patterns SHALL always be checked:
- `ssh\s|scp\s` (remote operations)
- `rm\s+-rf|drop\s|truncate\s|DELETE\s+FROM` (destructive operations)
- `sudo\s` (elevated operations)
- `docker\s|kubectl\s|podman\s` (container operations)

These base patterns are project-independent and cover universally relevant commands.

### Requirement: Hook deployment includes PreToolUse
The `set-deploy-hooks` script SHALL include `set-hook-memory-pretool` in a `PreToolUse` hook event with matcher `"Bash"`.

#### Scenario: Deploy adds PreToolUse hook
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **THEN** settings.json SHALL contain a `PreToolUse` entry matching `"Bash"` with `set-hook-memory-pretool`
- **AND** the timeout SHALL be 5 seconds
