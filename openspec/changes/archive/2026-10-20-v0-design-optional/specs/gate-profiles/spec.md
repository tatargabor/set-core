# gate-profiles — Delta Spec (v0-design-optional)

## ADDED Requirements

### Requirement: design_pipeline directive
The directive system SHALL support a `design_pipeline` field with valid values `"auto"` and `"none"`. The default SHALL be `"auto"`.

#### Scenario: Default value is auto
- **WHEN** no `design_pipeline` directive exists in orchestration.yaml
- **THEN** the effective value SHALL be `"auto"`

#### Scenario: Explicit none disables design pipeline
- **WHEN** orchestration.yaml contains `design_pipeline: "none"`
- **THEN** `has_design_pipeline()` SHALL return `False` regardless of `v0-export/` presence

#### Scenario: Explicit auto preserves detection
- **WHEN** orchestration.yaml contains `design_pipeline: "auto"`
- **THEN** `has_design_pipeline()` SHALL delegate to `detect_design_source()`

### Requirement: has_design_pipeline method on ProjectType ABC
The `ProjectType` ABC SHALL define `has_design_pipeline(project_path: Path, directives: dict | None = None) -> bool`. Base implementation SHALL return `False`. The method SHALL first check the `design_pipeline` directive — if `"none"`, return `False` without calling `detect_design_source()`. If `"auto"` or absent, delegate to `detect_design_source(project_path) != "none"`.

#### Scenario: Base class returns False
- **WHEN** `ProjectType.has_design_pipeline()` is called on the base ABC
- **THEN** it SHALL return `False`

#### Scenario: WebProjectType with v0-export returns True
- **WHEN** `WebProjectType.has_design_pipeline()` is called
- **AND** `detect_design_source()` returns `"v0"`
- **AND** no directive override
- **THEN** it SHALL return `True`

#### Scenario: WebProjectType without v0-export returns False
- **WHEN** `WebProjectType.has_design_pipeline()` is called
- **AND** `detect_design_source()` returns `"none"`
- **THEN** it SHALL return `False`

#### Scenario: Directive none overrides detection
- **WHEN** `WebProjectType.has_design_pipeline()` is called with directives `{"design_pipeline": "none"}`
- **AND** `detect_design_source()` would return `"v0"`
- **THEN** it SHALL return `False`
