## Requirements

### Requirement: Smoke test directives (DELTA)
The directive system SHALL support smoke test configuration.

#### Scenario: New directives
- **WHEN** directives are parsed
- **THEN** the following additional directives SHALL be recognized:
  - `smoke_command`: string (default: empty — disabled)
  - `smoke_timeout`: integer, seconds (default: 120)
  - `deploy_smoke_url`: string (default: empty — disabled)
  - `deploy_healthcheck`: string (default: `/api/health`)

#### Scenario: Directive validation
- **WHEN** `smoke_timeout` is not a positive integer
- **THEN** the system SHALL warn and use default (120)
- **WHEN** `deploy_healthcheck` is set without `deploy_smoke_url`
- **THEN** the system SHALL ignore `deploy_healthcheck` (no warning)

#### Scenario: Precedence
- **WHEN** smoke directives are resolved
- **THEN** the same 4-level precedence SHALL apply: CLI > YAML > in-doc > defaults
