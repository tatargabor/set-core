## MODIFIED Requirements

### Requirement: Engine loads plugin orchestration directives
The orchestration engine SHALL call `profile.get_orchestration_directives()` at startup and merge the returned directives with any directives from `orchestration.yaml`.

#### Scenario: Plugin directives active during orchestration
- **WHEN** the engine starts with a web project profile loaded
- **AND** the profile returns 7 orchestration directives
- **THEN** all 7 directives influence dispatch and post-merge behavior for the run

#### Scenario: No plugin directives available
- **WHEN** the engine starts with NullProfile active
- **THEN** only `orchestration.yaml` directives apply (existing behavior preserved)
