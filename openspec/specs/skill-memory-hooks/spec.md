# skill-memory-hooks Specification

## Purpose
TBD - created by archiving change shodh-memory-integration. Update Purpose after archive.
## Requirements
### Requirement: Archive skill saves decisions, learnings, and events
The `openspec-archive-change` SKILL.md SHALL include a Step 7 that, after the summary display, saves developer memory. Decisions from design.md SHALL be saved as type `Decision`, lessons learned as type `Learning`, and a change completion summary as type `Event`. All memory operations SHALL be conditional on `set-memory health` succeeding.

#### Scenario: Archive with shodh-memory running
- **WHEN** a change is archived and shodh-memory is running
- **THEN** decisions, learnings, and a completion event are saved to memory with appropriate tags (repo, change-name, schema/archive)

#### Scenario: Archive without shodh-memory
- **WHEN** a change is archived and shodh-memory is not running
- **THEN** the archive completes normally with no memory-related errors or warnings

### Requirement: Continue skill recalls past experience
The `openspec-continue-change` SKILL.md SHALL include a Step 2b that, before acting on status, recalls relevant past experience using the change name and keywords from the proposal. Retrieved memories SHALL inform artifact creation.

#### Scenario: Continue with relevant memories
- **WHEN** continuing a change and shodh-memory returns relevant past memories
- **THEN** the agent uses those memories to inform artifact creation

#### Scenario: Continue without shodh-memory
- **WHEN** continuing a change and shodh-memory is not running
- **THEN** artifact creation proceeds normally without memory recall

### Requirement: Fast-forward skill recalls past experience
The `openspec-ff-change` SKILL.md SHALL include a Step 3b that, before the artifact creation loop, recalls relevant past experience using the change name and user description.

#### Scenario: FF with relevant memories
- **WHEN** fast-forwarding a change and shodh-memory returns relevant memories
- **THEN** the agent keeps those memories in mind during artifact creation

#### Scenario: FF without shodh-memory
- **WHEN** fast-forwarding and shodh-memory is not running
- **THEN** artifact creation proceeds normally

### Requirement: Apply skill recalls patterns and saves learnings
The `openspec-apply-change` SKILL.md SHALL include a Step 4b for recall (after reading context files) and a Step 7 extension for remember (after showing status). Recall SHALL search for implementation patterns and errors. Remember SHALL save errors as `Observation`, patterns as `Learning`, and full completion as `Event`.

#### Scenario: Apply with recall
- **WHEN** implementing tasks and shodh-memory returns relevant past patterns
- **THEN** the agent uses those patterns to avoid known errors

#### Scenario: Apply saves errors encountered
- **WHEN** implementation encounters an error and shodh-memory is running
- **THEN** the error and its workaround are saved as an Observation memory

#### Scenario: Apply saves completion event
- **WHEN** all tasks are complete and shodh-memory is running
- **THEN** a completion event is saved to memory

#### Scenario: Apply without shodh-memory
- **WHEN** implementing tasks and shodh-memory is not running
- **THEN** implementation proceeds normally without memory operations

### Requirement: New skill checks for related past work
The `openspec-new-change` SKILL.md SHALL include a Step 1b that, after getting the user's description, recalls related past work. If relevant memories are found, a brief note SHALL be shown to the user.

#### Scenario: New change with related past work
- **WHEN** creating a new change and shodh-memory finds related past memories
- **THEN** a note is displayed: "Note: Related past work found — <summary>"

#### Scenario: New change without shodh-memory
- **WHEN** creating a new change and shodh-memory is not running
- **THEN** the change creation proceeds normally

### Requirement: All memory steps are silent on failure
Every memory step in every SKILL.md SHALL be conditional on `set-memory health` succeeding. If health fails, the step SHALL be skipped with no error, no warning, and no user-visible output.

#### Scenario: Silent degradation across all skills
- **WHEN** any OpenSpec skill runs a memory step and shodh-memory is not available
- **THEN** the step is silently skipped and the workflow continues unaffected

