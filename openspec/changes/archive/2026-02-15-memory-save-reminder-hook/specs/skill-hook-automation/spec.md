## MODIFIED Requirements

### Requirement: Automatic skill registration via hook
The system SHALL register the active skill for agent status display automatically when a skill is invoked, using a Claude Code PreToolUse hook instead of manual LLM instruction. Additionally, the hook SHALL create a `.memory` marker file when the invoked skill's SKILL.md contains `set-memory` instructions.

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

#### Scenario: Skill with set-memory instructions creates memory marker
- **WHEN** `wt-skill-start <skill-name>` is called
- **AND** the skill's SKILL.md file contains the string `set-memory`
- **THEN** a `.set-core/agents/<pid>.memory` marker file SHALL be created
- **AND** the marker file SHALL contain the skill name

#### Scenario: Skill without set-memory instructions skips marker
- **WHEN** `wt-skill-start <skill-name>` is called
- **AND** the skill's SKILL.md file does NOT contain the string `set-memory`
- **THEN** no `.memory` marker file SHALL be created
- **AND** any existing `.memory` file for this PID SHALL be removed
