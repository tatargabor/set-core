# Proposal: Plugin Deploy Architecture

## Why

The project-type plugin interface (`BaseProjectType`) has 15+ methods and is well-integrated at **runtime** (planning, dispatch, review, merge all call profile methods correctly). But the **deploy flow** (`set-project init`) doesn't properly delegate to plugins, and several plugin methods are defined but never wired into the engine:

1. **Web rules hardcoded in core** — `deploy.sh` checks `dir_part == web` and reads `project-type.yaml`. set-core should have zero knowledge of specific project types. If a new plugin (Python, mobile) needs its own rules, it should work without modifying set-core.

2. **Web rules live in set-core source** — The 7 `web/*.md` rule files under `.claude/rules/web/` belong in the `set-project-web` plugin package, not in set-core. set-core must not contain project-type-specific content at the source level.

3. **`NullProfile.rule_keyword_mapping()` contains web-specific paths** — The framework-agnostic fallback profile returns globs like `"web/auth-middleware.md"` and `"web/route-completeness.md"`. Non-web projects get web rule paths injected that don't exist. NullProfile should return `{}`.

4. **Rule deployment is split across two mechanisms** — Core rules deploy from `deploy.sh` (bash), template rules deploy from `deploy_templates()` (Python). Plugin should control ALL rule deployment through the existing Python mechanism in `set-project-base`.

5. **`get_verification_rules()` never integrated** — Plugins define 8+ verification rules but the verifier never loads or evaluates them. The interface exists in `set-project-base` ABC, `NullProfile` in set-core needs it too.

6. **`get_orchestration_directives()` never integrated** — Same pattern: plugins define 7+ directives but the engine never uses them. Interface exists in ABC, missing from `NullProfile`.

7. **`merge_strategies()` defined but never called** — Already defined in `NullProfile` (returns `[]`), but `merger.py` never calls it.

8. **Decomposer doesn't use plugin-specific planning hints** — `planning_rules()` provides text but there's no structured way for plugins to influence change decomposition.

## What Changes

### Phase 1: Plugin Rule Ownership (rule migration + deploy refactor)

**Principle**: set-core contains only generic rules. Project-type-specific rules live in their plugin package. The plugin controls what gets deployed via the existing Python `deploy_templates()` mechanism.

#### A. Migrate web rules from set-core to set-project-web

Move `set-core/.claude/rules/web/*.md` (7 files: auth-middleware, security-patterns, api-design, db-type-safety, route-completeness, schema-integrity, transaction-patterns) into `set-project-web/set_project_web/templates/nextjs/framework-rules/web/`.

The `deploy.py` `_PATH_MAPPINGS` in set-project-base gains a new entry:
```python
_PATH_MAPPINGS = {
    "rules/": ".claude/rules/",
    "framework-rules/": ".claude/rules/",  # framework rules deployed with set- prefix
}
```

The `_target_path()` function applies `set-` prefix for `framework-rules/` files to distinguish framework-provided rules from template rules.

After migration, consumer projects get the same files in the same locations — the source just moves from set-core to the plugin.

#### B. Simplify deploy.sh rule loop

Remove the hardcoded `web/` check (lines 190-199). deploy.sh only deploys top-level generic rules from `set-core/.claude/rules/` (no subdirectory traversal):
```bash
find "$src_rules" -maxdepth 1 -name '*.md' -print0
```

The `gui/` skip is also no longer needed (gui rules are set-core internal, and with maxdepth 1 they're never reached).

#### C. NullProfile cleanup

`NullProfile.rule_keyword_mapping()` returns `{}`. The `WebProjectType` already overrides this method with web-specific keyword→glob mappings.

#### D. Update flow

`set-project init` re-run triggers `deploy_templates()` which re-deploys all plugin rules (framework + template). The existing `force` parameter controls overwrite behavior. No version tracking needed — `cp` overwrites.

### Phase 2: Verification Rules Integration

Wire `get_verification_rules()` into the verify gate:

- Add `get_verification_rules()` to `NullProfile` (returns `[]`) — the interface contract lives in core, implementations in plugins.
- Engine loads plugin verification rules at startup via `profile.get_verification_rules()` — **runtime loading**, not file-based (same pattern as all other profile methods).
- Verifier evaluates applicable rules during spec_verify gate.
- Each rule has a `check` type — the verifier dispatches to check implementations.
- Start with the existing 6 check types from SCHEMA.md.

### Phase 3: Orchestration Directives Integration

Wire `get_orchestration_directives()` into the engine:

- Add `get_orchestration_directives()` to `NullProfile` (returns `[]`).
- Engine loads plugin directives at startup via `profile.get_orchestration_directives()` — runtime loading.
- Directives influence dispatch (e.g., serialize i18n changes, skip parallel dispatch for DB-touching changes).
- Directives influence post-merge (e.g., `prisma generate` after schema changes).

### Phase 4: Merge Strategies (interface complete, needs engine wiring only)

Wire `merge_strategies()` into merger:

- Interface already exists in `NullProfile` (returns `[]`).
- `merger.py` calls `profile.merge_strategies()` to get file-protection rules.
- Protected files get special merge handling (e.g., theirs-wins for lockfiles, ours-wins for schema files).
- **Lowest effort phase** — only engine-side wiring needed.

### Phase 5: Decomposer Planning Hints

Enhance plugin influence on decomposition:

- Add `decompose_hints()` method to profile interface.
- Returns **self-describing hints** that carry their own prompt text, so the plugin fully controls rendering:
  ```python
  def decompose_hints(self) -> list[str]:
      return [
          "For each product category in the database schema enum, create a separate listing page task — do not use one category as a representative example.",
          "Every new user-facing route must have a corresponding i18n key task.",
      ]
  ```
- Planner appends these hints to the decompose prompt.
- This keeps plugin logic in the plugin (no registry of hint keys in core).

## Capabilities

### New Capabilities
- `plugin-rule-deploy`: Plugin controls ALL rule deployment through Python deploy mechanism
- `verification-rule-integration`: Plugin-defined verification rules run during verify gate
- `orchestration-directive-integration`: Plugin-defined directives influence engine behavior
- `merge-strategy-integration`: Plugin-defined merge strategies protect specific files
- `decompose-hints`: Plugin provides natural-language decomposition hints

### Modified Capabilities
- `deploy-flow`: deploy.sh handles only generic core rules; plugin rules deploy via Python `deploy_templates()`
- `verify-gate`: Accepts plugin verification rules alongside spec coverage
- `orchestration-engine`: Loads and applies plugin directives
- `merger`: Applies plugin merge strategies
- `null-profile`: Fully empty — no project-type-specific knowledge

## Verification Criteria

### Phase 1: Deploy Parity Test

Before-and-after snapshot comparison ensures the migration produces identical results in consumer projects:

```bash
# 1. BEFORE migration: snapshot current deploy
set-project init web --project-dir /tmp/test-before
find /tmp/test-before/.claude/rules/ -type f | sort > /tmp/before-files.txt
find /tmp/test-before/.claude/rules/ -type f -exec md5sum {} \; | sort > /tmp/before-checksums.txt

# 2. AFTER migration: deploy with new mechanism
set-project init web --project-dir /tmp/test-after
find /tmp/test-after/.claude/rules/ -type f | sort > /tmp/after-files.txt
find /tmp/test-after/.claude/rules/ -type f -exec md5sum {} \; | sort > /tmp/after-checksums.txt

# 3. VERIFY: identical file list and content
diff /tmp/before-files.txt /tmp/after-files.txt          # same files
diff /tmp/before-checksums.txt /tmp/after-checksums.txt  # same content
```

Must verify:
- All 7 `web/set-*.md` framework rules present in consumer `.claude/rules/web/`
- All 17 template rules present in consumer `.claude/rules/`
- Generic core rules (top-level `set-*.md`) still deployed by deploy.sh
- `set-` prefix applied correctly to framework-rules, not to template rules
- Re-run (`set-project init` on existing project) updates changed rules

### Phase 2-5: Runtime Integration Tests

- `profile.get_verification_rules()` called by verifier → rules appear in gate output
- `profile.get_orchestration_directives()` called by engine → directives logged at startup
- `profile.merge_strategies()` called by merger → protected files get special handling
- `profile.decompose_hints()` called by templates → hints appear in planning prompt
- NullProfile (no plugin) → all methods return empty, no crashes

## Risk

**Medium**. Key risks and mitigations:

| Risk | Mitigation |
|------|-----------|
| Web rules missing after migration (deploy gap) | Verify consumer project has identical `.claude/rules/` before and after |
| set-core loses web rules for own development | set-project-web installed in editable mode during set-core development; profile loads and dispatcher uses rules normally |
| Plugin not installed → no rules deployed | NullProfile returns `{}` everywhere; deploy.sh still deploys generic core rules; `set-project init` requires a project type argument |
| `framework-rules/` vs `rules/` confusion | Clear naming: `rules/` = project template conventions, `framework-rules/` = framework guardrails (set- prefixed) |
| `get_verification_rules()` / `get_orchestration_directives()` not in NullProfile | Phase 2-3 explicitly add them to NullProfile first |
| Decompose hints too vague or too prescriptive | Hints carry their own prompt text — plugin author controls specificity |

## Scope

### In Scope
- Migrate `web/*.md` rules from set-core to set-project-web plugin package
- Extend `deploy.py` `_PATH_MAPPINGS` for `framework-rules/` → `.claude/rules/`
- Simplify deploy.sh (remove subdirectory filtering, top-level only)
- NullProfile cleanup (all methods return `{}` / `[]`)
- Verification rule integration into verify gate
- Orchestration directive integration into engine
- Merge strategy wiring in merger
- Decompose hints for planning

### Out of Scope
- Creating new project type plugins (set-project-python, set-project-mobile)
- Changing the plugin entry_points registration mechanism
- Redesigning the template deployment mechanism (deploy_templates stays as-is)
- Adding new check types to SCHEMA.md (use existing 6 for now)
- Prefix convention change (set- prefix stays for framework rules)

## Cross-Repo Changes

### set-core
| Phase | Change |
|-------|--------|
| 1 | Delete `.claude/rules/web/` (7 files) |
| 1 | Simplify `deploy.sh` rule loop (remove web/ hardcode, maxdepth 1) |
| 1 | `NullProfile.rule_keyword_mapping()` → return `{}` |
| 2 | Add `get_verification_rules()` to `NullProfile` (returns `[]`) |
| 2 | Wire `profile.get_verification_rules()` into verifier |
| 3 | Add `get_orchestration_directives()` to `NullProfile` (returns `[]`) |
| 3 | Wire `profile.get_orchestration_directives()` into engine |
| 4 | Wire `profile.merge_strategies()` into merger |
| 5 | Add `decompose_hints()` to `NullProfile`, wire into templates.py |

### set-project-base
| Phase | Change |
|-------|--------|
| 1 | `deploy.py`: Add `framework-rules/` to `_PATH_MAPPINGS` with set- prefix logic |
| 1 | `deploy.py`: `_target_path()` applies set- prefix for framework-rules/ files |

### set-project-web
| Phase | Change |
|-------|--------|
| 1 | Add `templates/nextjs/framework-rules/web/` with 7 migrated rule files |
| 1 | Update `templates/nextjs/manifest.yaml` to include framework-rules |
| 5 | Add `decompose_hints()` to `WebProjectType` |
