# v0-design-source Specification

## Purpose
TBD - created by archiving change design-binding-completeness. Update Purpose after archive.
## Requirements
### Requirement: V0DesignSourceProvider implements scan_hygiene
The `V0DesignSourceProvider` SHALL implement a `scan_hygiene(project_path: Path) -> list[HygieneFinding]` method invoking the v0 hygiene scanner against the project's `v0-export/` directory. Findings are returned as structured `HygieneFinding` dataclasses (file, line, rule, severity, message, suggested_fix).

#### Scenario: Provider returns scanner findings
- **WHEN** `V0DesignSourceProvider.scan_hygiene(project_path)` is called
- **AND** `v0-export/` contains components with MOCK arrays
- **THEN** the result includes a finding with `rule="mock-arrays-inline"`, `severity="critical"`

### Requirement: V0DesignSourceProvider implements get_shell_components
The `V0DesignSourceProvider` SHALL implement a `get_shell_components(project_path: Path) -> list[str]` method returning the manifest's `shared` list (paths relative to the design source root, e.g. `v0-export/components/search-palette.tsx`).

#### Scenario: Provider returns shared list
- **WHEN** `V0DesignSourceProvider.get_shell_components(project_path)` is called
- **AND** the manifest's `shared` contains `[v0-export/components/site-header.tsx, v0-export/components/search-palette.tsx]`
- **THEN** the method returns those paths verbatim

