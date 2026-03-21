## MODIFIED Requirements

### Requirement: NullProfile has no project-type-specific knowledge
`NullProfile` SHALL return empty values for all methods. It SHALL NOT contain references to specific project types, rule file paths, or domain-specific keywords.

#### Scenario: rule_keyword_mapping returns empty
- **WHEN** NullProfile is active
- **THEN** `rule_keyword_mapping()` returns `{}`

#### Scenario: All list methods return empty
- **WHEN** NullProfile is active
- **THEN** `get_verification_rules()` returns `[]`
- **AND** `get_orchestration_directives()` returns `[]`
- **AND** `merge_strategies()` returns `[]`
- **AND** `decompose_hints()` returns `[]`

### Requirement: NullProfile defines all profile interface methods
Every method that plugins can override SHALL have a default implementation in NullProfile to prevent AttributeError when no plugin is loaded.

#### Scenario: New methods accessible on NullProfile
- **WHEN** code calls `profile.get_verification_rules()` on a NullProfile instance
- **THEN** the call succeeds and returns `[]` (no AttributeError)
