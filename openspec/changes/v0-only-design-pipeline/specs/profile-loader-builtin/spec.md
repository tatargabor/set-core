# Spec: Profile Loader Builtin (delta)

## ADDED Requirements

### Requirement: WebProjectType implements design-source provider methods

`WebProjectType` (in `modules/web/set_project_web/project_type.py`) SHALL implement the new `ProjectType` ABC methods (`detect_design_source`, `copy_design_source_slice`, `get_design_dispatch_context`) for v0 design source.

#### Scenario: WebProjectType.detect_design_source with v0-export present
- **GIVEN** `<project_path>/v0-export/` directory exists
- **WHEN** `WebProjectType().detect_design_source(project_path)` is called
- **THEN** it returns `"v0"`

#### Scenario: WebProjectType.detect_design_source without v0-export
- **GIVEN** `<project_path>/v0-export/` does not exist
- **WHEN** `WebProjectType().detect_design_source(project_path)` is called
- **THEN** it returns `"none"`
- **AND** the project gracefully degrades to no-design-source mode

#### Scenario: WebProjectType.copy_design_source_slice populates dest
- **GIVEN** `detect_design_source() == "v0"`
- **AND** `<project_path>/docs/design-manifest.yaml` is present and valid
- **WHEN** `WebProjectType().copy_design_source_slice(change_name, scope, dest)` is called
- **THEN** the implementation invokes the web module's manifest matcher
- **AND** copies route-matched files + shared files from `<project_path>/v0-export/` into `dest/` preserving structure
- **AND** returns the list of copied file paths

#### Scenario: WebProjectType.get_design_dispatch_context returns markdown
- **WHEN** `WebProjectType().get_design_dispatch_context(change_name, scope, project_path)` is called
- **THEN** it returns a markdown block containing:
  - Pointer to `openspec/changes/<change_name>/design-source/` (constructed using the change_name parameter)
  - Listing of route + shared files included
  - Token quick-reference parsed from `<project_path>/shadcn/globals.css` (consumer project root) or `<project_path>/v0-export/app/globals.css` (fallback)
  - Reference to design-bridge.md rule

#### Scenario: WebProjectType registers design-fidelity gate
- **WHEN** `WebProjectType` is loaded by the profile loader
- **THEN** it SHALL register the `design-fidelity` gate in the gate registry
- **AND** the gate is enabled when `detect_design_source() == "v0"`, skipped otherwise
