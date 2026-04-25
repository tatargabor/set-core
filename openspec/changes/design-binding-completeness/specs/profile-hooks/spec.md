## ADDED Requirements

### Requirement: Provider exposes scan_design_hygiene method
The `ProjectType` ABC SHALL expose a `scan_design_hygiene(project_path: Path) -> list[HygieneFinding]` method. The default implementation returns an empty list. Profile implementations (e.g. `WebProjectType`) override to delegate to their `DesignSourceProvider`.

#### Scenario: Web profile delegates to V0 provider
- **WHEN** `WebProjectType.scan_design_hygiene(project_path)` is called
- **AND** `detect_design_source(project_path) == "v0"`
- **THEN** the call delegates to `V0DesignSourceProvider.scan_hygiene(project_path)`
- **AND** returns the v0-specific findings

#### Scenario: Non-web profile returns empty
- **WHEN** a profile that does not implement design hygiene is asked
- **THEN** the call returns `[]` without error

### Requirement: Provider exposes get_shell_components method
The `ProjectType` ABC SHALL expose a `get_shell_components(project_path: Path) -> list[str]` method returning the manifest's `shared` list (as paths relative to the design source root). Default implementation returns `[]`.

#### Scenario: Reads shared from manifest
- **WHEN** `WebProjectType.get_shell_components(project_path)` is called
- **AND** `<project>/docs/design-manifest.yaml` exists with `shared:` list
- **THEN** the method returns the `shared` paths
