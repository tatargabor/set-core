## ADDED Requirements

### Requirement: Rollback preview warns about active issues outside rollback scope

`recovery.render_preview` SHALL append a "Warnings" section listing any active issue (state in INVESTIGATING, DIAGNOSED, AWAITING_APPROVAL, FIXING) whose `affected_change` is NOT in the rollback's `rollback_changes` set. The rollback still proceeds; the warning is advisory so operators can manually close or dismiss orphaned issues before the rollback executes.

#### Scenario: Active issue inside rollback scope — not listed
- **WHEN** render_preview runs for a plan that rolls back change "foo"
- **AND** an active issue's `affected_change` equals "foo"
- **THEN** the warning section SHALL NOT mention this issue (it will be cleaned up by rollback)

#### Scenario: Active issue outside rollback scope — listed
- **WHEN** render_preview runs for a plan that rolls back change "foo"
- **AND** an active issue's `affected_change` is "bar" (NOT in rollback_changes)
- **THEN** the warning section SHALL include one line per such issue: id, state, affected_change, and fix-iss child name if any

#### Scenario: No active outside-scope issues — section omitted
- **WHEN** no active issues reference changes outside the rollback scope
- **THEN** the warning section SHALL NOT appear in the preview output

#### Scenario: Terminal-state issues ignored
- **WHEN** an issue's state is RESOLVED, DISMISSED, MUTED, CANCELLED, SKIPPED, or FAILED
- **THEN** it SHALL NOT be listed in the warning section regardless of scope

#### Scenario: Registry unreadable — graceful degradation
- **WHEN** the issue registry file is missing or malformed
- **THEN** `render_preview` SHALL NOT raise
- **AND** SHALL proceed without the warning section (a DEBUG log MAY note the registry access failure)
