## MODIFIED Requirements

### Requirement: Claude Code config dimension
The system SHALL check `.claude/settings.json` for permissions, hooks, agents, and rules.
The memory-hook check **inverts**: the presence of a `set-hook-memory` entry is the finding
and its absence is the healthy state. Before this change the scan reported ❌ on absence and
told the user to run `set-deploy-hooks` — which after the removal would have instructed
every project to reinstall exactly what was taken out.

#### Scenario: Check permissions
- **WHEN** `.claude/settings.json` exists and has `permissions.allow` entries
- **THEN** report status ✅ with count of allow/deny rules

#### Scenario: Missing permissions
- **WHEN** `.claude/settings.json` has no `permissions` key or empty `allow` array
- **THEN** report status ❌ with guidance to add safe commands for the detected stack

#### Scenario: Check memory hooks
- **WHEN** `.claude/settings.json` has hooks containing `set-hook-memory`
- **THEN** report status ❌ with the count found
- **AND** the guidance SHALL be to run `set-deploy-hooks`, which removes them
- **AND** the guidance SHALL NOT suggest installing or restoring any memory hook

#### Scenario: Missing memory hooks
- **WHEN** hooks do not contain `set-hook-memory` entries
- **THEN** report status ✅
- **AND** no guidance SHALL be emitted for this check

#### Scenario: Check agents
- **WHEN** `.claude/agents/` directory contains `.md` files
- **THEN** report status ✅ listing agent names and their model settings

#### Scenario: No agents directory
- **WHEN** `.claude/agents/` does not exist or is empty
- **THEN** report status ⚠️ with guidance pointing to reference.md for recommended agents

#### Scenario: Check rules
- **WHEN** `.claude/rules/` directory contains `.md` files
- **THEN** report status ✅ listing rule files and their path globs

#### Scenario: No project-specific rules
- **WHEN** `.claude/rules/` only contains set-core managed rules (prefixed `set-`) or is empty
- **THEN** report status ⚠️ with guidance to create path-scoped rules for distinct code areas
