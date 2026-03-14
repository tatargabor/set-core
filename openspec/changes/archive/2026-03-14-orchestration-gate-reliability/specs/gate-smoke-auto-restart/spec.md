## ADDED Requirements

### Requirement: Auto-start dev server on health_check failure
When smoke health_check fails and a `smoke_dev_server_command` directive is configured, the system SHALL attempt to start the dev server before falling back to `smoke_blocked` status.

#### Scenario: Health check fails with dev server command configured
- **WHEN** health_check returns failure AND `smoke_dev_server_command` is set in directives
- **THEN** the system SHALL execute the dev server command in the background, wait for health_check to succeed (with extended timeout of 60s), and proceed with smoke tests if successful

#### Scenario: Dev server start succeeds
- **WHEN** the dev server command is executed AND health_check succeeds within the extended timeout
- **THEN** the system SHALL proceed with smoke tests normally and record the dev server PID for cleanup

#### Scenario: Dev server start fails
- **WHEN** the dev server command is executed AND health_check still fails after the extended timeout
- **THEN** the system SHALL kill the started process, set status to `smoke_blocked`, and send sentinel notification

#### Scenario: No dev server command configured
- **WHEN** health_check fails AND `smoke_dev_server_command` is NOT set
- **THEN** the system SHALL use existing behavior (immediate `smoke_blocked` status)

### Requirement: Dev server cleanup on orchestrator exit
The orchestrator SHALL kill any dev server processes it started when the orchestrator exits or receives a termination signal.

#### Scenario: Orchestrator receives SIGTERM
- **WHEN** the orchestrator exits (normal or signal)
- **THEN** any dev server PID started by auto-restart SHALL be killed
