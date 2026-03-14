## MODIFIED Requirements

### Requirement: Scoped smoke fix agent
When smoke tests fail, the fix agent SHALL receive change-specific context. Additionally, the system SHALL support a `smoke_dev_server_command` directive for auto-starting the dev server.

#### Scenario: Dev server command directive parsed
- **WHEN** orchestration.yaml contains `smoke_dev_server_command: "<command>"`
- **THEN** the directive parser SHALL store it and make it available to the smoke pipeline
