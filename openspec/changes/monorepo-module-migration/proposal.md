# Proposal: monorepo-module-migration

## Why

Project-type modules (base, web, example) live in separate repositories, causing:

1. **entry_points registration failure** — editable installs silently break, NullProfile fallback, gates skip
2. **Coordinated commits** — interface changes require matching commits across repos
3. **Architecture leaks** — web-specific logic migrates into set-core core (verifier.py has package.json parsing)
4. **Unnecessary indirection** — base module is just an ABC + 3 universal rules; it's framework infra, not a plugin

## What Changes

### Base module → absorbed into set-core
- `base.py` ABC + dataclasses (`ProjectType`, `VerificationRule`, `OrchestrationDirective`, etc.) → `lib/set_orch/profile_types.py` (new file)
- `BaseProjectType` universal rules/directives → `CoreProfile` class in `lib/set_orch/profile_loader.py`
- `resolver.py` (`ProjectTypeResolver`) → `lib/set_orch/profile_resolver.py` (new file)
- `deploy.py` (template resolution/deployment) → `lib/set_orch/profile_deploy.py` (new file)
- `feedback.py` (`FeedbackStore`) → `lib/set_orch/profile_feedback.py` (new file)
- `cli.py` → integrated into `bin/set-project`
- **NullProfile** inherits from `ProjectType` ABC (no more duck-typing)
- **CoreProfile** replaces BaseProjectType — universal rules built into set-core

### Web + Example modules → `modules/` directory
- `set-project-web` → `modules/web/` (source + pyproject.toml + tests only)
- `set-project-example` → `modules/example/` (source + pyproject.toml + tests only)
- **Stripped**: openspec/, CLAUDE.md, README.md, .claude/, set/, .git/
- **WebProjectType** changes parent: `BaseProjectType` → `CoreProfile` (from set_orch)
- **pyproject.toml** kept per module for standalone install/fork capability

### Web-specific code removed from set-core core
- `_read_package_json_scripts()` removed from verifier.py
- `_auto_detect_e2e_command()` simplified: only calls `profile.detect_e2e_command()`, no package.json/playwright fallback
- All web detection logic stays in `WebProjectType.detect_e2e_command()`

### Profile loader updated
- Resolution: entry_points → direct import → built-in modules/ → NullProfile
- Built-in module step: check `modules/{type}/set_project_{type}/` relative to set-core root
- `NullProfile` inherits from `ProjectType` ABC

## Capabilities

### New Capabilities
- `profile-types`: ABC and dataclasses for project type plugins (moved from base)
- `profile-resolver`: Rule/directive merging with YAML overlay (moved from base)
- `profile-deploy`: Template file deployment (moved from base)
- `core-profile`: Universal rules/directives built into set-core

### Modified Capabilities
- `profile-loader`: Built-in module fallback, CoreProfile instead of NullProfile for core rules
- `verify-gate`: Web-specific auto-detect removed from core
- `deploy`: Template resolution from modules/ path

## Impact

- **New files**: `lib/set_orch/profile_types.py`, `lib/set_orch/profile_resolver.py`, `lib/set_orch/profile_deploy.py`, `lib/set_orch/profile_feedback.py`, `modules/web/`, `modules/example/`
- **Modified files**: `lib/set_orch/profile_loader.py`, `lib/set_orch/verifier.py`, `bin/set-project`, `pyproject.toml`
- **Deleted external dependency**: `set-project-base` no longer needed as separate package
- **Risk**: Medium — import paths change for web module; profile_loader gets new resolution step
- **Tests**: Profile loader tests updated; module tests moved to `modules/{name}/tests/`
