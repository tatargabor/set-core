## Tasks: Planning Quality Profiles — Profile-Engine Bridge

### Phase A: Non-Breaking Foundation

- [x] A1: Extend ProjectType ABC in wt-project-base
  - File: `wt-project-base/wt_project_base/base.py`
  - Add 12 new methods with default (no-op) implementations to `ProjectType` ABC:
    - `planning_rules() -> str` (default: "")
    - `security_rules_paths(project_path) -> List[Path]` (default: [])
    - `security_checklist() -> str` (default: "")
    - `generated_file_patterns() -> List[str]` (default: [])
    - `lockfile_pm_map() -> List[tuple[str, str]]` (default: [])
    - `detect_package_manager(project_path) -> Optional[str]` (default impl uses lockfile_pm_map)
    - `detect_test_command(project_path) -> Optional[str]` (default: None)
    - `detect_build_command(project_path) -> Optional[str]` (default: None)
    - `detect_dev_server(project_path) -> Optional[str]` (default: None)
    - `bootstrap_worktree(project_path, wt_path) -> bool` (default: True)
    - `post_merge_install(project_path) -> bool` (default: True)
    - `ignore_patterns() -> List[str]` (default: [])
  - All methods are concrete (not abstract) — backward compatible
  - Bump version to 0.2.0
  - Verify: existing BaseProjectType and WebProjectType still import and instantiate without changes

- [x] A2: Create profile_loader.py in wt-tools
  - File: `lib/wt_orch/profile_loader.py` (NEW)
  - `NullProfile` class — mirrors all 12 ABC methods with empty/no-op returns
  - `load_profile(project_path=".") -> ProjectType` — reads `wt/plugins/project-type.yaml`, loads via entry_points, singleton cache
  - `reset_cache()` — for testing
  - Default `project_path="."` resolves to absolute path (engine CWD convention — see Constraint 1 in design)
  - Graceful fallback: any failure → NullProfile (log warning, don't crash)

- [x] A3: Unit tests for profile_loader
  - File: `tests/test_profile_loader.py` (NEW)
  - Test: no project-type.yaml → NullProfile
  - Test: valid yaml + entry_point → loads WebProjectType
  - Test: invalid yaml → NullProfile (graceful)
  - Test: missing plugin package → NullProfile (graceful)
  - Test: singleton cache works (load twice, same object)
  - Test: reset_cache() clears and reloads
  - Test: NullProfile returns empty/None for all 12 methods

### Phase B: Implement Web Profile Methods

- [x] B1: Implement new methods in WebProjectType
  - File: `wt-project-web/wt_project_web/project_type.py`
  - Implement all 12 new methods (pseudocode in design Component 2):
    - `planning_rules()` — reads from bundled `planning_rules.txt`
    - `security_rules_paths()` — globs `.claude/rules/` for security/auth files, fallback to template dir
    - `security_checklist()` — web-specific markdown checklist (IDOR, middleware, XSS, etc.)
    - `generated_file_patterns()` — tsbuildinfo, lockfiles, .next, dist, build
    - `lockfile_pm_map()` — pnpm/yarn/bun/npm lockfile mappings
    - `detect_test_command()` — package.json scripts (test, test:unit, test:ci)
    - `detect_build_command()` — package.json scripts (build:ci, build)
    - `detect_dev_server()` — package.json scripts.dev
    - `bootstrap_worktree()` — frozen-lockfile install, fallback to unfrozen
    - `post_merge_install()` — normal pm install
    - `ignore_patterns()` — node_modules, .next, dist, build, .turbo
  - Bump version to 0.2.0

- [x] B2: Create planning_rules.txt for web profile
  - File: `wt-project-web/wt_project_web/planning_rules.txt` (NEW)
  - Extract L295-317 from `wt-tools/lib/wt_orch/templates.py` `_PLANNING_RULES` (Playwright E2E block)
  - Also add framework-specific security patterns that supplement the core security block:
    - Next.js middleware.ts pattern for route protection
    - Prisma where clause ownership patterns
    - CSRF/XSS patterns for React/Next.js
  - **CRITICAL**: Must include the Playwright E2E block — templates.py split (C5) depends on this

### Phase C: Wire Engine to Profile

Each step follows the pattern: `profile.method() → if None/empty → legacy fallback`.

- [x] C1: Wire config.py — PM, test, dev server, install
  - File: `lib/wt_orch/config.py`
  - `detect_package_manager()` → `profile.detect_package_manager()` first, legacy fallback
  - `auto_detect_test_command()` → `profile.detect_test_command()` first, legacy fallback
  - `detect_dev_server()` → insert `profile.detect_dev_server()` as step 3 in cascade (before package.json inline check), generic fallback (docker-compose, Makefile, manage.py) stays in core
  - `install_dependencies()` → `profile.post_merge_install()` for non-NullProfile, legacy fallback
  - Design ref: Component 4f, 4l

- [x] C2: Wire dispatcher.py — PM detection + bootstrap
  - File: `lib/wt_orch/dispatcher.py`
  - `_detect_package_manager()` → `profile.detect_package_manager()` first, `LOCKFILE_PM_MAP` fallback
  - `bootstrap_worktree()` → keep core env file copy, delegate dep install to `profile.bootstrap_worktree()`, legacy fallback
  - Design ref: Component 4c

- [x] C3: Wire builder.py — PM + build command
  - File: `lib/wt_orch/builder.py`
  - `_detect_pm()` → `profile.detect_package_manager()` first, legacy fallback
  - `_detect_build_cmd()` → `profile.detect_build_command()` first, legacy fallback
  - Design ref: Component 4e

- [x] C4: Wire merger.py — post-merge install + build check
  - File: `lib/wt_orch/merger.py`
  - `_post_merge_deps_install()` → `profile.post_merge_install()` for non-NullProfile, legacy fallback
  - `_post_merge_build_check()` → `profile.detect_package_manager()` + `profile.detect_build_command()` first, legacy fallback
  - Design ref: Component 4d

- [x] C5: Wire templates.py — split _PLANNING_RULES + proposal checklist
  - File: `lib/wt_orch/templates.py`
  - **BLOCKED on B2**: planning_rules.txt must exist with Playwright block before this step
  - Split `_PLANNING_RULES` into `_PLANNING_RULES_CORE` (everything except L295-317) + keep `_PLANNING_RULES` as legacy
  - New `_get_planning_rules(project_path)` → core + `profile.planning_rules()`, fallback to full `_PLANNING_RULES`
  - Wire into `render_planning_prompt()` — replace `{_PLANNING_RULES}` refs with `_get_planning_rules()` call
  - `render_proposal()` → `profile.security_checklist()` first, generic `_GENERIC_SECURITY_CHECKLIST` fallback
  - Note: `render_proposal()` needs `project_path` parameter added
  - Design ref: Component 4a, 4a-bis

- [x] C6: Wire planner.py — test command detection
  - File: `lib/wt_orch/planner.py`
  - `_auto_detect_test_command()` → `profile.detect_test_command()` first, legacy fallback (inline PM detection stays as fallback)
  - Design ref: Component 4j

- [x] C7: Wire milestone.py — dev server + dependency install
  - File: `lib/wt_orch/milestone.py`
  - `_detect_dev_server()` → insert `profile.detect_dev_server()` after directive check, before package.json inline check
  - `_install_dependencies()` → `profile.post_merge_install()` for non-NullProfile, legacy fallback (see Constraint 3 in design — uses post_merge_install not bootstrap_worktree)
  - Design ref: Component 4k

- [x] C8: Wire verifier.py — security rules for retry
  - File: `lib/wt_orch/verifier.py`
  - New `_load_security_rules(wt_path)` → `profile.security_rules_paths(wt_path)` first, `_load_web_security_rules(wt_path)` legacy fallback
  - Replace call site of `_load_web_security_rules()` with new function
  - **MUST complete before D3** (deploy.sh web rule removal) — see Constraint 2 in design
  - Design ref: Component 4b

- [x] C9: Wire digest.py — ignore patterns
  - File: `lib/wt_orch/digest.py`
  - Extract `_CORE_IGNORE_PATTERNS = {"archive", ".git", "__pycache__", ".venv"}`
  - New `_get_ignore_patterns()` → core | `set(profile.ignore_patterns())`
  - Replace `_IGNORE_PATTERNS` usage in `_should_ignore()` with `_get_ignore_patterns()`
  - Design ref: Component 4g

### Phase D: Bash Integration

- [x] D1: Wire bin/wt-merge — generated file patterns from profile
  - File: `bin/wt-merge`
  - Read `wt/plugins/.generated-file-patterns` file if it exists, append to `GENERATED_FILE_PATTERNS` array
  - The file is one pattern per line, written by `profile_loader.py` or `wt-project init`
  - Keep existing hardcoded patterns as base (backward compat)
  - Design ref: Component 4h

- [x] D2: Wire bin/wt-new — profile-aware bootstrap
  - File: `bin/wt-new`
  - Replace `bootstrap_dependencies()` bash function with Python call to `profile.bootstrap_worktree()`
  - Legacy fallback: if Python call fails, run current bash PM detection
  - Design ref: Component 4i

- [x] D3: deploy.sh — stop deploying web/ rules to consumers
  - File: `lib/project/deploy.sh`
  - **BLOCKED on C8**: verifier must use profile before we remove web rule deployment
  - In `_deploy_skills()` rule loop: skip files where `dir_part == "web"` (already skips `gui`)
  - Web rules now come exclusively from wt-project-web templates via `deploy.py`
  - wt-tools' own `.claude/rules/web/` stays — used for self-development
  - Design ref: Component 5

- [x] D4: Write .generated-file-patterns at init/startup
  - Profile loader or `wt-project init` writes `wt/plugins/.generated-file-patterns` for bash consumption
  - One pattern per line from `profile.generated_file_patterns()`
  - Called at engine startup (profile_loader) or at `wt-project init` time

### Phase E: Cleanup

- [x] E1: Remove legacy PM detection duplications
  - Remove `LOCKFILE_PM_MAP` from `dispatcher.py` (replaced by profile)
  - Remove `_detect_pm()` from `builder.py` (replaced by profile)
  - Remove inline PM detection from `planner.py:_auto_detect_test_command()` (replaced by profile)
  - Remove inline PM detection from `config.py:auto_detect_test_command()` (replaced by profile)
  - Remove inline PM detection from `milestone.py:_detect_dev_server()` + `_install_dependencies()` (replaced by profile)
  - Total: 7 independent PM detection implementations consolidated into 1 profile method
  - Keep `config.py:detect_package_manager()` as the ONE canonical fallback (called by profile loader default impl)

- [x] E2: Remove legacy planning rules constant
  - Remove `_PLANNING_RULES` full constant from `templates.py` (replaced by `_PLANNING_RULES_CORE` + profile)
  - Only do this after E2E validation confirms profile-based planning works correctly

- [x] E3: Remove legacy GENERATED_FILE_PATTERNS from dispatcher.py
  - Remove `GENERATED_FILE_PATTERNS` set from `dispatcher.py`
  - This set is now profile-provided + core patterns in `bin/wt-merge`

- [x] E4: Add TODO markers for future legacy removal
  - Mark remaining legacy fallback code blocks with `# TODO(profile-cleanup): remove after profile adoption confirmed`
  - These blocks are the "if profile returns None, do legacy" paths
  - They stay until we're confident all consumer projects have profile configured
