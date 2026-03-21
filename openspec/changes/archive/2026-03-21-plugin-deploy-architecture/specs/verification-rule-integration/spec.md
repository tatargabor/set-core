## ADDED Requirements

## IN SCOPE
- Verifier loads plugin verification rules via profile method
- Rules evaluated during verify gate alongside existing YAML-based rules
- NullProfile provides empty default

## OUT OF SCOPE
- Adding new check types beyond existing 6 in SCHEMA.md
- Changing the VerificationRule dataclass in set-project-base

### Requirement: NullProfile defines get_verification_rules
`NullProfile` in `profile_loader.py` SHALL define `get_verification_rules()` returning an empty list.

#### Scenario: NullProfile returns empty rules
- **WHEN** no plugin is loaded and NullProfile is active
- **THEN** `profile.get_verification_rules()` returns `[]`

### Requirement: Verifier loads plugin verification rules
The verifier SHALL call `profile.get_verification_rules()` during the rules gate evaluation and merge the returned rules with any YAML-defined rules from `project-knowledge.yaml`.

#### Scenario: Plugin rules loaded at verify time
- **WHEN** the verify gate runs for a change
- **AND** the loaded profile returns 8 verification rules
- **THEN** all 8 rules are evaluated alongside YAML-defined rules

#### Scenario: Plugin rule overrides YAML rule on ID collision
- **WHEN** both the plugin and `project-knowledge.yaml` define a rule with the same ID
- **THEN** the plugin rule takes precedence

### Requirement: Plugin verification rules use existing check types
Plugin-provided `VerificationRule` objects SHALL use the `check` field to specify one of the existing check types. The verifier dispatches to the same check implementations used for YAML-defined rules.

#### Scenario: Plugin rule with cross-file-key-parity check
- **WHEN** a plugin returns a rule with `check: "cross-file-key-parity"`
- **THEN** the verifier evaluates it using the cross-file-key-parity check implementation
