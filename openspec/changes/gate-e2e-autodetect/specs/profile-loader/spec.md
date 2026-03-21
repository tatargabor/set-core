## IN SCOPE
- Direct import fallback when entry_points lookup returns empty
- NullProfile.detect_e2e_command method addition

## OUT OF SCOPE
- Changing how entry_points registration works (pip/setuptools concern)
- Supporting multiple profiles simultaneously

### Requirement: Profile loader shall fall back to direct import
When `entry_points(group='set_tools.project_types')` returns no matching entry for the configured type name, the loader SHALL attempt a direct import using the naming convention `set_project_{type_name}` module with class lookup. If the direct import succeeds, the loaded profile SHALL be cached and returned. If it fails, NullProfile SHALL be returned as before.

#### Scenario: Entry points empty but package importable
- **GIVEN** project-type.yaml contains `type: web`
- **AND** `entry_points(group='set_tools.project_types')` returns 0 entries
- **AND** `set_project_web` module is importable
- **WHEN** `load_profile()` is called
- **THEN** the loader SHALL import `set_project_web` directly
- **AND** SHALL instantiate and return the profile class
- **AND** SHALL log "Loaded profile via direct import fallback"

#### Scenario: Entry points empty and package not importable
- **GIVEN** project-type.yaml contains `type: web`
- **AND** `entry_points()` returns 0 entries
- **AND** `set_project_web` is NOT importable
- **WHEN** `load_profile()` is called
- **THEN** the loader SHALL return NullProfile
- **AND** SHALL log the import failure at warning level

### Requirement: NullProfile shall provide detect_e2e_command interface
NullProfile SHALL define `detect_e2e_command(project_path: str) -> Optional[str]` returning None. Project-type plugins MAY override this to auto-detect E2E commands.

#### Scenario: NullProfile returns None for e2e detection
- **WHEN** `NullProfile().detect_e2e_command("/any/path")` is called
- **THEN** it SHALL return None
