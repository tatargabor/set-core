## IN SCOPE
- Built-in module resolution step in profile_loader.py
- NullProfile inherits from ProjectType ABC
- CoreProfile class with universal rules

## OUT OF SCOPE
- Changing NullProfile method signatures
- Removing entry_points support

### Requirement: Profile loader shall resolve built-in modules
After entry_points and direct import fallback, the loader SHALL check `modules/{type_name}/set_project_{type_name}/` relative to set-core root. If found, load from there.

#### Scenario: Built-in module loaded
- **GIVEN** entry_points and direct import fail
- **AND** `modules/web/set_project_web/` exists
- **WHEN** `load_profile()` is called with type "web"
- **THEN** it SHALL load WebProjectType from the built-in module path

#### Scenario: Entry_points override built-in
- **GIVEN** an external package registers "web" via entry_points
- **WHEN** `load_profile()` is called
- **THEN** the external entry_points version SHALL win

### Requirement: NullProfile shall inherit from ProjectType ABC
NullProfile SHALL extend ProjectType from profile_types.py instead of being a standalone class with duck-typed methods.
