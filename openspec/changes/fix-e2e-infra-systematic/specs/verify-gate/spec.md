## ADDED Requirements

### Requirement: Config drift warning

On engine startup, the engine SHALL compare the mtime of `set/orchestration/config.yaml` against `set/orchestration/directives.json`. If `config.yaml` is newer (the user edited it after directives were generated), a `CONFIG_DRIFT` event SHALL be emitted with `{yaml_mtime, directives_mtime, delta_secs}` and a WARNING log line SHALL note that the edit is not active until orchestrator restart or manual regeneration.

#### Scenario: User edited yaml after orchestrator start
- **GIVEN** `directives.json` was written at `T0` and `config.yaml` was edited at `T0 + 3600` seconds
- **WHEN** the engine starts a new supervisor at `T0 + 7200`
- **THEN** `CONFIG_DRIFT` event SHALL be emitted
- **AND** a WARNING log SHALL read: "config.yaml is 3600s newer than directives.json — changes not active until regenerated"

#### Scenario: No drift
- **GIVEN** `directives.json` was written after the latest `config.yaml` edit
- **WHEN** the engine starts
- **THEN** no `CONFIG_DRIFT` event SHALL be emitted

#### Scenario: Missing directives.json (fresh init)
- **GIVEN** `directives.json` does not exist
- **WHEN** the engine starts
- **THEN** no `CONFIG_DRIFT` event SHALL be emitted (directives will be generated from yaml)
