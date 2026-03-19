## ADDED Requirements

### Requirement: Automatic skill registration via hook
The system SHALL register the active skill for agent status display automatically when a skill is invoked, using a Claude Code PreToolUse hook instead of manual LLM instruction.

#### Scenario: Skill invoked triggers hook
- **WHEN** a Claude agent invokes a skill (e.g., `/opsx:explore`)
- **THEN** the PreToolUse hook fires before the skill prompt is processed
- **AND** the hook extracts the skill name from the Skill tool input JSON
- **AND** calls `wt-skill-start <skill-name>` to write the per-PID skill file

#### Scenario: Hook runs in wt-managed directory
- **WHEN** the hook fires in a directory with `.set-core/`
- **THEN** `wt-skill-start` writes `.set-core/agents/<claude-pid>.skill`
- **AND** no legacy `current_skill` file is written

#### Scenario: Hook runs outside wt-managed directory
- **WHEN** the hook fires in a directory without `.set-core/`
- **THEN** `wt-skill-start` exits silently (no `.set-core` to write to)

#### Scenario: Multiple agents invoke skills simultaneously
- **WHEN** two Claude agents on the same worktree invoke different skills
- **THEN** each agent's hook writes to its own `<pid>.skill` file
- **AND** the files do not interfere with each other

### Requirement: SKILL.md files do not contain manual skill registration
All SKILL.md files SHALL NOT contain manual `wt-skill-start` instructions since registration is handled by the hook.

#### Scenario: Skill prompt loaded
- **WHEN** a SKILL.md prompt is expanded for the LLM
- **THEN** it does not contain a `wt-skill-start` bash instruction block
