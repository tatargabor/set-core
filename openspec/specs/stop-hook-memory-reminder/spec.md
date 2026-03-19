## Requirements

### Requirement: Stop hook outputs memory reminder when skill has memory steps
The `set-hook-stop` script SHALL check for a `.memory` marker file alongside the active `.skill` file. When the marker exists, the hook SHALL output a reminder message to stdout that Claude Code injects into the agent's conversation.

#### Scenario: Skill with memory hooks active
- **WHEN** the Stop event fires
- **AND** `.set-core/agents/<pid>.skill` exists
- **AND** `.set-core/agents/<pid>.memory` exists
- **THEN** the hook SHALL output a reminder to stdout: `[MEMORY REMINDER] Active skill has set-memory hooks. Run your recall/remember steps before finishing.`
- **AND** the hook SHALL still perform its normal timestamp refresh

#### Scenario: Skill without memory hooks
- **WHEN** the Stop event fires
- **AND** `.set-core/agents/<pid>.skill` exists
- **AND** `.set-core/agents/<pid>.memory` does NOT exist
- **THEN** the hook SHALL NOT output any reminder
- **AND** shall perform normal timestamp refresh only

#### Scenario: No active skill
- **WHEN** the Stop event fires
- **AND** no `.skill` file exists for the current agent
- **THEN** the hook SHALL NOT output any reminder

#### Scenario: Reminder is output only once per skill session
- **WHEN** the Stop hook outputs a memory reminder
- **THEN** the `.memory` marker SHALL remain (not deleted)
- **AND** the reminder SHALL be output on every Stop event while the skill is active
- **NOTE** This is intentional — repeated reminders increase compliance. The skill clears both `.skill` and `.memory` on completion.

### Requirement: Memory marker cleaned up with skill file
When a skill session ends (`.skill` file is removed by `set-skill-start` for a new skill or by session cleanup), the corresponding `.memory` file SHALL also be removed.

#### Scenario: New skill replaces old skill
- **WHEN** `set-skill-start <new-skill>` is called
- **AND** `.set-core/agents/<pid>.memory` exists from the previous skill
- **THEN** the old `.memory` file SHALL be removed
- **AND** a new `.memory` file SHALL only be created if the new skill also has memory hooks

#### Scenario: Agent session ends
- **WHEN** the agent process exits and cleanup runs
- **THEN** both `.set-core/agents/<pid>.skill` and `.set-core/agents/<pid>.memory` SHALL be cleaned up
