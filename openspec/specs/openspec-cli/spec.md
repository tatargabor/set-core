# Openspec Cli Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: set-openspec init command
The `set-openspec init` command SHALL run `openspec init --tools claude` in the main repo path for a given project. It SHALL accept a `--project` flag or auto-detect from `git rev-parse --show-toplevel`. It SHALL exit 0 on success, non-zero on failure.

#### Scenario: Initialize OpenSpec in a project
- **WHEN** user runs `set-openspec init` in a git repo without `openspec/config.yaml`
- **THEN** the command runs `openspec init --tools claude` in the repo root and creates the `openspec/` directory structure and `.claude/skills/openspec-*` skill files

#### Scenario: Init when already initialized
- **WHEN** user runs `set-openspec init` in a repo that already has `openspec/config.yaml`
- **THEN** the command exits with a warning message "OpenSpec already initialized" and exit code 0

### Requirement: set-openspec update command
The `set-openspec update` command SHALL run `openspec update` in the main repo path. It SHALL accept a `--project` flag or auto-detect from git root.

#### Scenario: Update OpenSpec skills
- **WHEN** user runs `set-openspec update` in a repo with OpenSpec initialized
- **THEN** the command runs `openspec update` in the repo root, updating SKILL.md files to the latest version

#### Scenario: Update when not initialized
- **WHEN** user runs `set-openspec update` in a repo without OpenSpec
- **THEN** the command exits with error "OpenSpec not initialized" and exit code 1

### Requirement: set-openspec status command with JSON output
The `set-openspec status --json` command SHALL return a JSON object with: `installed` (bool — `openspec/config.yaml` exists), `version` (string or null — from `openspec --version`), `changes_active` (int — count of non-archived change directories), `skills_present` (bool — `.claude/skills/openspec-*` directories exist). The command SHALL use filesystem checks (not `openspec list --json`) to keep execution under 10ms.

#### Scenario: Status when OpenSpec installed
- **WHEN** user runs `set-openspec status --json` in a repo with OpenSpec
- **THEN** the command outputs `{"installed": true, "version": "1.1.1", "changes_active": 2, "skills_present": true}` (values reflect actual state)

#### Scenario: Status when OpenSpec not installed
- **WHEN** user runs `set-openspec status --json` in a repo without OpenSpec
- **THEN** the command outputs `{"installed": false, "version": null, "changes_active": 0, "skills_present": false}`

#### Scenario: Status performance
- **WHEN** the command runs
- **THEN** it completes in under 10ms by using filesystem checks only (no subprocess calls to `openspec` CLI)
