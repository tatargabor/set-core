# Auto Memory Hooks Deploy Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Memory hooks included in default deploy config
The `set-deploy-hooks` script SHALL include `set-hook-memory-recall` (UserPromptSubmit, timeout 15), `set-hook-memory-save` (Stop, timeout 30), `set-hook-memory-warmstart` (SessionStart, timeout 10), `set-hook-memory-pretool` (PreToolUse matcher "Bash", timeout 5), and `set-hook-memory-posttool` (PostToolUseFailure matcher "Bash", timeout 5) in the default hook configuration alongside the existing `set-hook-skill` and `set-hook-stop` hooks.

#### Scenario: Fresh deploy includes all memory hooks
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** no `.claude/settings.json` exists
- **THEN** the created settings.json SHALL contain all 5 memory hooks across their respective events
- **AND** `set-hook-memory-warmstart` SHALL be in SessionStart with timeout 10
- **AND** `set-hook-memory-recall` SHALL be in UserPromptSubmit with timeout 15
- **AND** `set-hook-memory-pretool` SHALL be in PreToolUse matching "Bash" with timeout 5
- **AND** `set-hook-memory-posttool` SHALL be in PostToolUseFailure matching "Bash" with timeout 5
- **AND** `set-hook-memory-save` SHALL be in Stop with timeout 30

#### Scenario: Memory hooks have correct timeouts
- **WHEN** `set-deploy-hooks` creates or updates settings.json
- **THEN** `set-hook-memory-warmstart` SHALL have `"timeout": 10`
- **AND** `set-hook-memory-recall` SHALL have `"timeout": 15`
- **AND** `set-hook-memory-pretool` SHALL have `"timeout": 5`
- **AND** `set-hook-memory-posttool` SHALL have `"timeout": 5`
- **AND** `set-hook-memory-save` SHALL have `"timeout": 30`

### Requirement: Upgrade existing configs with memory hooks
The `set-deploy-hooks` script SHALL add new memory hooks (warmstart, pretool, posttool) to existing settings.json files that have the base hooks and original memory hooks but are missing the new hooks.

#### Scenario: Existing config without new hooks gets upgraded
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** settings.json already contains `set-hook-memory-recall` and `set-hook-memory-save`
- **AND** settings.json does NOT contain `set-hook-memory-warmstart`
- **THEN** the script SHALL add SessionStart, PreToolUse, and PostToolUseFailure hook entries
- **AND** SHALL create a backup before modification

#### Scenario: Canonical config is not modified
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** settings.json PreToolUse has only `Skill` matcher (activity-track.sh, no set-hook-memory entries)
- **AND** settings.json PostToolUse has only `Read` and `Bash` matchers (set-hook-memory)
- **THEN** the script SHALL exit 0 without modification

#### Scenario: Over-provisioned config is downgraded
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** settings.json PreToolUse has set-hook-memory entries for Read, Edit, Write, Bash, Task, Grep
- **AND** settings.json PostToolUse has set-hook-memory entries for Read, Edit, Write, Bash, Task, Grep
- **THEN** the script SHALL remove stale entries and exit 0
- **AND** PreToolUse SHALL contain only the Skill/activity-track.sh entry
- **AND** PostToolUse SHALL contain only Read and Bash set-hook-memory entries

### Requirement: No-memory flag skips memory hooks
The `set-deploy-hooks` script SHALL accept a `--no-memory` flag that deploys only the base hooks without any memory hooks.

#### Scenario: Deploy without memory hooks
- **WHEN** `set-deploy-hooks --no-memory /path/to/project` is called
- **THEN** settings.json SHALL contain `set-hook-skill` and `set-hook-stop`
- **AND** SHALL NOT contain any `set-hook-memory-*` hooks

### Requirement: Documentation of automatic memory hooks
The developer memory documentation SHALL include a section describing all 5 automatic memory hook layers and how they complement each other.

#### Scenario: Docs describe all hook layers
- **WHEN** a developer reads `docs/developer-memory.md`
- **THEN** they SHALL find descriptions of L1 (warmstart), L2 (recall), L3 (pretool), L4 (posttool), and L5 (save)
