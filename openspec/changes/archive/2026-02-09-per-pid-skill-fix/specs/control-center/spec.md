## MODIFIED Requirements

### Requirement: Status Command
The system SHALL provide a `wt-status` command that displays worktree and agent status.

#### Scenario: Per-agent skill display
- **WHEN** wt-status checks a worktree with agents
- **THEN** each agent's skill is read exclusively from `.set-core/agents/<pid>.skill`
- **AND** no fallback to `.set-core/current_skill` is used

#### Scenario: Agent with no skill file
- **WHEN** an agent PID has no corresponding `.set-core/agents/<pid>.skill` file
- **THEN** the skill field for that agent is null
- **AND** no legacy fallback file is consulted

#### Scenario: Multiple agents with different skills
- **WHEN** two agents on the same worktree have different per-PID skill files
- **THEN** each agent row shows its own skill name independently
