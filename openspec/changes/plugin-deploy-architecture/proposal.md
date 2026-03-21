# Proposal: Plugin Deploy Architecture

## Why

The project-type plugin interface (`BaseProjectType`) has 15+ methods and is well-integrated at **runtime** (planning, dispatch, review, merge all call profile methods correctly). But the **deploy flow** (`set-project init`) doesn't properly delegate to plugins:

1. **Web rules hardcoded in core** — `deploy.sh` checks `dir_part == web` and reads `project-type.yaml`. If a Python or mobile plugin needs its own rules, the core deploy script needs modification. The plugin should control what gets deployed.

2. **`NullProfile.rule_keyword_mapping()` contains web-specific paths** — The framework-agnostic fallback profile returns globs like `"web/auth-middleware.md"` and `"web/route-completeness.md"`. Non-web projects get web rule paths injected into dispatched agents — rules that don't exist in their `.claude/rules/`. This actively contradicts the modular architecture.

3. **`get_verification_rules()` never integrated** — Plugins define 11+ verification rules (i18n completeness, route registration, migration safety, etc.) but these are only counted for logging at init time. The verifier never loads or evaluates them. These methods exist only in set-project-web (`BaseProjectType`/`WebProjectType`), not in `NullProfile` — so the interface contract needs to be added to the core profile first.

4. **`get_orchestration_directives()` never integrated** — Same pattern: plugins define 7+ directives but the engine never uses them.

5. **`merge_strategies()` defined but never called** — Already defined in `NullProfile` (interface ready), but `merger.py` never calls it. Lower effort: only needs engine-side wiring.

6. **Rule deployment is split** — Core rules deploy from `deploy.sh`. Plugin template deploy (`wt_project_base.cli deploy-templates`) deploys application scaffolds but not Claude rules. No mechanism for plugins to inject `.claude/rules/<plugin>/` files.

7. **Decomposer doesn't use plugin-specific planning context** — `planning_rules()` provides text but there's no structured way for plugins to influence change decomposition (e.g., "ensure a listing page for every schema category").

## What Changes

### Phase 1: Plugin Rule Deployment (core deploy refactor)

Replace the hardcoded `web/` check in `deploy.sh` with a **manifest-based mechanism** (no Python subprocess calls from bash):

- At `set-project init` time, the existing `wt_project_base.cli deploy-templates` call already runs Python in the plugin's context. Extend it to also write a **`wt/plugins/deploy-manifest.json`** containing the list of rule files the plugin wants deployed (paths relative to the plugin package).
- `deploy.sh` reads this manifest and copies the listed rule files to `.claude/rules/<subdir>/` with `set-` prefix.
- If no manifest exists (no plugin, NullProfile), deploy.sh deploys only core rules (current behavior minus the `web/` hardcode).
- **Migration sequence**: The manifest mechanism must be implemented in `wt_project_base` and `set-project-web` FIRST, verified that it produces the same rule set, and THEN the hardcoded `web/` check removed from `deploy.sh`. A brief overlap period where both mechanisms work is acceptable.
- **Fallback**: During the overlap, `deploy.sh` keeps the `web/` hardcode as a fallback if no manifest is found (graceful degradation).

**NullProfile cleanup**: Move web-specific entries out of `NullProfile.rule_keyword_mapping()` — it should return `{}`. The `WebProjectType` already overrides this method (added in the `web-route-completeness-rules` change). After cleanup, NullProfile has no web knowledge.

### Phase 2: Verification Rules Integration

Wire `get_verification_rules()` into the verify gate:

- Add `get_verification_rules()` to `NullProfile` (returns `[]`) — the interface contract lives in core, implementations in plugins.
- Engine loads plugin verification rules at startup via `profile.get_verification_rules()` — **runtime loading**, not file-based (avoids staleness; same pattern as all other profile methods).
- Verifier evaluates applicable rules during spec_verify gate.
- Each rule has a `check` type — the verifier dispatches to check implementations.
- Start with the existing 6 check types from SCHEMA.md.
- Optionally write `wt/plugins/verification-rules.json` as a diagnostic artifact (not authoritative — runtime loading is the source of truth).

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
- `plugin-rule-deploy`: Plugin controls which rules get deployed via manifest
- `verification-rule-integration`: Plugin-defined verification rules run during verify gate
- `orchestration-directive-integration`: Plugin-defined directives influence engine behavior
- `merge-strategy-integration`: Plugin-defined merge strategies protect specific files
- `decompose-hints`: Plugin provides natural-language decomposition hints

### Modified Capabilities
- `deploy-flow`: Core deploy reads plugin manifest instead of hardcoding directories
- `verify-gate`: Accepts plugin verification rules alongside spec coverage
- `orchestration-engine`: Loads and applies plugin directives
- `merger`: Applies plugin merge strategies
- `null-profile`: Cleaned up — no web-specific knowledge

## Risk

**Medium**. Key risks and mitigations:

| Risk | Mitigation |
|------|-----------|
| Breaking `set-project init` for projects without plugins | NullProfile implements all new methods returning `[]`; fallback in deploy.sh if no manifest |
| Manifest stale after plugin update | Manifest only for deploy-time rules; runtime uses `profile.*()` directly |
| Migration window between old/new deploy logic | Keep `web/` hardcode as fallback until manifest is confirmed working |
| `get_verification_rules()` / `get_orchestration_directives()` not in NullProfile | Phase 2-3 explicitly add them to NullProfile first |
| Decompose hints too vague or too prescriptive | Hints carry their own prompt text — plugin author controls specificity |
| Non-web projects get web rules from NullProfile | Phase 1 cleanup moves web keyword mappings out of NullProfile |

## Scope

### In Scope
- Plugin rule deployment via manifest mechanism
- NullProfile cleanup (remove web-specific keyword mappings)
- Verification rule integration into verify gate
- Orchestration directive integration into engine
- Merge strategy wiring in merger
- Decompose hints for planning
- Remove hardcoded `web/` check from deploy.sh (after manifest works)

### Out of Scope
- Creating new project type plugins (set-project-python, set-project-mobile)
- Changing the plugin entry_points registration mechanism
- Redesigning the template deployment mechanism (wt_project_base.cli)
- Adding new check types to SCHEMA.md (use existing 6 for now)
- Modifying `BaseProjectType` in set-project-base (changes go through NullProfile in core)

## Cross-Repo Dependencies

| Phase | set-core | set-project-base | set-project-web |
|-------|----------|-------------------|-----------------|
| 1 | deploy.sh manifest reader, NullProfile cleanup | deploy-manifest writer in CLI | WebProjectType.deploy_rules() returning rule list |
| 2 | NullProfile.get_verification_rules(), verifier wiring | (none) | (already implemented) |
| 3 | NullProfile.get_orchestration_directives(), engine wiring | (none) | (already implemented) |
| 4 | merger.py wiring | (none) | (already implemented in WebProjectType) |
| 5 | NullProfile.decompose_hints(), planner wiring | (none) | WebProjectType.decompose_hints() |
