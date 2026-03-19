## ADDED Requirements

### Requirement: Skill registration on start
Skills SHALL register themselves by writing to a status file when they start.

#### Scenario: Skill writes status file
- **WHEN** a skill starts executing
- **THEN** it writes `<skill-name>|<unix-timestamp>` to `.set-core/current_skill`
- **AND** creates the `.set-core` directory if it doesn't exist

#### Scenario: Skill registration format
- **WHEN** the opsx:explore skill starts
- **THEN** the status file contains `opsx:explore|1706356800` (example timestamp)

### Requirement: Skill status reading
The wt-status command SHALL read and report the current skill from the status file.

#### Scenario: Read fresh skill status
- **WHEN** wt-status runs and a skill was registered within the last 30 minutes
- **THEN** the skill name is included in the agent status output

#### Scenario: Ignore stale skill status
- **WHEN** wt-status runs and the skill timestamp is older than 30 minutes
- **THEN** the skill name is NOT included (status file is stale)

#### Scenario: No status file exists
- **WHEN** wt-status runs and no `.set-core/current_skill` file exists
- **THEN** no skill name is reported (graceful handling)

### Requirement: Skill helper script
A helper script SHALL simplify skill registration for skill authors.

#### Scenario: Use wt-skill-start helper
- **WHEN** a skill runs `wt-skill-start "opsx:explore"`
- **THEN** the status file is created with correct format and timestamp

### Requirement: Skill display in GUI
The Control Center SHALL display the current skill name instead of PID.

#### Scenario: Show skill name in status column
- **WHEN** an agent is running with a registered skill
- **THEN** the status shows "waiting (opsx:explore)" instead of "waiting (12345)"

#### Scenario: Show status without skill
- **WHEN** an agent is running but no skill is registered
- **THEN** the status shows just "waiting" without parenthetical info
