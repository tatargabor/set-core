# Tasks: Plugin Deploy Architecture

## Phase 1: Plugin Rule Ownership

### 1.1 set-project-base: deploy.py framework-rules mapping
- [x] 1.1.1 Add `"framework-rules/"` to `_PATH_MAPPINGS` in `set-project-base/set_project_base/deploy.py`
- [x] 1.1.2 Update `_target_path()` to apply `set-` prefix for files under `framework-rules/` path
- [x] 1.1.3 Verify template `rules/` files still deploy WITHOUT `set-` prefix (no regression)

### 1.2 set-project-web: migrate framework rules
- [x] 1.2.1 Create `set-project-web/set_project_web/templates/nextjs/framework-rules/web/` directory
- [x] 1.2.2 Copy 7 rule files from `set-core/.claude/rules/web/` to the new directory: auth-middleware.md, security-patterns.md, api-design.md, db-type-safety.md, route-completeness.md, schema-integrity.md, transaction-patterns.md
- [x] 1.2.3 Update `set-project-web/set_project_web/templates/nextjs/manifest.yaml` — add all `framework-rules/web/*.md` files to the `core` list

### 1.3 set-core: remove web rules and simplify deploy
- [x] 1.3.1 Delete `set-core/.claude/rules/web/` directory (7 files)
- [x] 1.3.2 Simplify deploy.sh rule loop: replace `find` with `find -maxdepth 1 -name '*.md'` (remove lines 188-199 web/ hardcode and gui/ skip)
- [x] 1.3.3 Clean `NullProfile.rule_keyword_mapping()` in `profile_loader.py` — return `{}`

### 1.4 Verification: deploy parity
- [x] 1.4.1 Verify `_target_path()` maps `framework-rules/web/auth-middleware.md` → `.claude/rules/web/set-auth-middleware.md`
- [x] 1.4.2 Verify `_target_path()` maps `rules/auth-conventions.md` → `.claude/rules/auth-conventions.md` (no set- prefix)
- [x] 1.4.3 All 3 repos' tests pass (set-project-base 48, set-project-web 7, set-core 539+ non-GUI)
- [x] 1.4.4 WebProjectType.rule_keyword_mapping() returns set- prefixed globs

## Phase 2: Verification Rules Integration

- [x] 2.1 Add `get_verification_rules()` method to `NullProfile` in `profile_loader.py` returning `[]`
- [x] 2.2 In `verifier.py` `evaluate_verification_rules()`, call `profile.get_verification_rules()` and merge with YAML-defined rules (plugin rules take precedence on ID collision)
- [x] 2.3 Verify: WebProjectType.get_verification_rules() returns 15 rules

## Phase 3: Orchestration Directives Integration

- [x] 3.1 Add `get_orchestration_directives()` method to `NullProfile` in `profile_loader.py` returning `[]`
- [x] 3.2 In `engine.py`, call `profile.get_orchestration_directives()` at startup and merge with `orchestration.yaml` directives
- [x] 3.3 Wire `action: "serialize"` directives into dispatch logic — matching changes dispatched sequentially
- [x] 3.4 Wire `action: "post-merge"` directives into post-merge logic — run specified command after merge
- [x] 3.5 Verify: WebProjectType.get_orchestration_directives() returns 11 directives

## Phase 4: Merge Strategies

- [x] 4.1 In `merger.py`, call `profile.merge_strategies()` before merge operations
- [x] 4.2 Apply returned strategies: `theirs` strategy auto-resolves conflicts using remote version, `ours` uses local version
- [x] 4.3 Verify: NullProfile.merge_strategies() returns [] (WebProjectType inherits from BaseProjectType which doesn't define it — future addition)

## Phase 5: Decompose Hints

- [x] 5.1 Add `decompose_hints()` method to `NullProfile` in `profile_loader.py` returning `[]`
- [x] 5.2 In `templates.py` `render_planning_prompt()`, call `profile.decompose_hints()` and append returned strings after planning rules section
- [x] 5.3 Add `decompose_hints()` to `WebProjectType` in `set-project-web/project_type.py` returning web-specific decomposition hints
- [x] 5.4 Verify: planning prompt includes plugin hints when profile returns them
