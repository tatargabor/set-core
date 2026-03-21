## 1. Absorb base module into set-core

- [x] 1.1 Create `lib/set_orch/profile_types.py` — move ABC `ProjectType` + all dataclasses from base
- [x] 1.2 Create `lib/set_orch/profile_resolver.py` — move `ProjectTypeResolver` from base, update imports
- [x] 1.3 Create `lib/set_orch/profile_deploy.py` — move template deploy functions from base, update imports
- [x] 1.4 Create `lib/set_orch/profile_feedback.py` — move feedback system from base
- [x] 1.5 Add `CoreProfile(ProjectType)` to `lib/set_orch/profile_loader.py` with 3 verification rules + 4 orchestration directives
- [x] 1.6 Make `NullProfile` inherit from `ProjectType` ABC
- [x] 1.7 Update all imports in copied files: `set_project_base.base` → `set_orch.profile_types`
- [x] 1.8 Create backwards compatibility shim: `lib/set_project_base/__init__.py`

## 2. Move web module to modules/web/

- [x] 2.1 Copy `set_project_web/` package to `modules/web/set_project_web/`
- [x] 2.2 Copy `pyproject.toml` to `modules/web/pyproject.toml`
- [x] 2.3 Copy `tests/` to `modules/web/tests/`
- [x] 2.4 Strip: openspec/, CLAUDE.md, README.md, .claude/, set/, docs/, .git/, __pycache__/
- [x] 2.5 Update imports: `BaseProjectType` → `CoreProfile`, `set_project_base.base` → `set_orch.profile_types`
- [x] 2.6 Update `base.py` re-exports to use `set_orch.profile_types`
- [x] 2.7 Remove `set-project-base` from pyproject.toml dependencies
- [x] 2.8 Verify `__init__.py` exports WebProjectType correctly

## 3. Move example module to modules/example/

- [x] 3.1 Copy `set_project_example/` to `modules/example/set_project_example/`
- [x] 3.2 Copy `pyproject.toml` to `modules/example/pyproject.toml`
- [x] 3.3 Strip __pycache__/
- [x] 3.4 Update imports: `BaseProjectType` → `CoreProfile`
- [x] 3.5 Remove `set-project-base` from pyproject.toml dependencies

## 4. Profile loader — built-in module resolution

- [x] 4.1 Add step 3 in load_profile(): check `modules/{type_name}/set_project_{type_name}/` relative to set-core root
- [x] 4.2 Log: "Loaded profile via built-in module"
- [x] 4.3 Tests updated for new resolution order and CoreProfile

## 5. Remove web-specific code from verifier.py

- [x] 5.1 Remove `_read_package_json_scripts()` function
- [x] 5.2 Simplify `_auto_detect_e2e_command()`: only `profile.detect_e2e_command()`, return result or ""
- [x] 5.3 Update tests: remove package.json/playwright direct tests, add profile-delegation tests

## 6. bin/set-project update

- [ ] 6.1 Change `from set_project_base.deploy import ...` → `from set_orch.profile_deploy import ...`
- [ ] 6.2 Add modules/ template path fallback in deploy.sh

## 7. Branch rename master → main

- [x] 7.1 Rename local branch: `git branch -m master main`
- [x] 7.2 Code references to "master" in git fallback lists kept (consumer compat)

## 8. Verification

- [x] 8.1 Run tests: 43 pass + 1 pre-existing failure
- [x] 8.2 Backwards compat: `from set_project_base import BaseProjectType` → CoreProfile ✓
- [x] 8.3 Web module: WebProjectType loads from built-in modules/, inherits 3 core + 12 web rules ✓
- [x] 8.4 Integration: temp project → profile loads from modules/ ✓
- [x] 8.5 `_auto_detect_e2e_command` delegates to profile only ✓
