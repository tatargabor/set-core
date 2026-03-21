## MODIFIED Requirements

### Requirement: Verify gate evaluates plugin verification rules
The verify gate SHALL load verification rules from the active profile via `profile.get_verification_rules()` and evaluate them alongside rules defined in `project-knowledge.yaml`.

#### Scenario: Plugin rules merged with YAML rules
- **WHEN** the verify gate runs
- **AND** `project-knowledge.yaml` defines 3 rules and the plugin defines 8 rules
- **THEN** all 11 rules are evaluated (or 10 if one ID collides, with plugin taking precedence)

#### Scenario: No plugin rules available
- **WHEN** the verify gate runs with NullProfile active
- **THEN** only YAML-defined rules are evaluated (existing behavior preserved)
