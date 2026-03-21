## IN SCOPE
- Base module absorbed into set-core (ABC, resolver, deploy, feedback)
- Web and example modules moved to modules/ (stripped to source + pyproject.toml + tests)
- Web-specific code removed from verifier.py core
- CoreProfile replaces BaseProjectType as inheritance root
- Backwards compatibility shim for `import set_project_base`
- Master → main branch rename

## OUT OF SCOPE
- Changing the plugin method interface
- Creating new module types
- Changing template content inside modules

### Requirement: Base module shall be absorbed into set-core
The ABC interface (`ProjectType`), dataclasses (`VerificationRule`, `OrchestrationDirective`, etc.), `ProjectTypeResolver`, template deploy functions, and feedback system SHALL move from `set-project-base` into `lib/set_orch/profile_*.py` files.

#### Scenario: ABC and dataclasses in profile_types.py
- **WHEN** a plugin needs to import the base interface
- **THEN** `from set_orch.profile_types import ProjectType, VerificationRule` SHALL work
- **AND** all 5 dataclasses and the ABC SHALL be available

#### Scenario: CoreProfile provides universal rules
- **GIVEN** CoreProfile is instantiated
- **WHEN** `get_verification_rules()` is called
- **THEN** it SHALL return 3 rules: file-size-limit, no-secrets, todo-tracking
- **AND** `get_orchestration_directives()` SHALL return 4 directives

#### Scenario: Backwards compatibility shim
- **WHEN** an external plugin does `from set_project_base import BaseProjectType`
- **THEN** it SHALL resolve to `CoreProfile` from set_orch
- **AND** SHALL NOT require set-project-base to be installed

### Requirement: Modules shall contain only source, pyproject.toml, and tests
Module directories under `modules/` SHALL NOT contain openspec/, CLAUDE.md, README.md, .claude/, set/, or any other standalone-repo scaffolding.

#### Scenario: Web module structure
- **GIVEN** set-project-web is migrated to modules/web/
- **THEN** modules/web/ SHALL contain: `set_project_web/`, `pyproject.toml`, `tests/`
- **AND** SHALL NOT contain: openspec/, CLAUDE.md, README.md, .claude/, set/, docs/

### Requirement: WebProjectType shall inherit from CoreProfile
WebProjectType SHALL change its parent class from `BaseProjectType` to `CoreProfile` imported from `set_orch.profile_loader`.

#### Scenario: Web inherits core rules
- **WHEN** `WebProjectType().get_verification_rules()` is called
- **THEN** it SHALL include the 3 CoreProfile universal rules
- **AND** SHALL include its own 14 web-specific rules

### Requirement: Web-specific code shall be removed from verifier.py
`_read_package_json_scripts()` SHALL be removed. `_auto_detect_e2e_command()` SHALL only call `profile.detect_e2e_command()` and return its result (or empty string).

### Requirement: Default branch shall be renamed to main
The repository default branch SHALL be renamed from `master` to `main`. All references to `master` in code, configs, and documentation SHALL be updated.
