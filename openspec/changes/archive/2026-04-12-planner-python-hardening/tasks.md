# Tasks: planner-python-hardening

## 1. Profile ABC Extension

- [x] 1.1 Verify `planning_rules(self) -> str` already exists in `ProjectType` ABC (`lib/set_orch/profile_types.py` line ~128). If present, ensure docstring says "Module-specific planning rules injected into planner prompt." If missing, add it with default `""`. [REQ: profile-provides-planning-rules]
- [x] 1.2 Add `cross_cutting_files(self) -> list[str]` to `ProjectType` ABC in `lib/set_orch/profile_types.py` — default returns `[]`. Docstring: "File patterns needing serialization when touched by multiple changes." [REQ: profile-provides-cross-cutting-file-list]

## 2. Web Module Implementation

- [x] 2.1 Implement `planning_rules()` in `WebProjectType` (`modules/web/set_project_web/project_type.py`) — return string with: schema/migration before data-layer ordering, CRUD test requirements per change, i18n namespace convention. Extract these verbatim from current `_PLANNING_RULES_CORE` in `templates.py`. [REQ: profile-provides-planning-rules]
- [x] 2.2 Implement `cross_cutting_files()` in `WebProjectType` — extract from current hardcoded `_DEFAULT_CROSS_CUTTING_FILES` in `planner.py` (currently: `layout.tsx`, `middleware.ts`, `middleware.js`, `next.config.js`, `next.config.ts`, `next.config.mjs`, `tailwind.config.ts`, `tailwind.config.js`). Keep all existing entries, do not add new ones beyond what is currently tracked. [REQ: profile-provides-cross-cutting-file-list]

## 3. Core Rules Cleanup

- [x] 3.1 Remove web-specific rules from `_PLANNING_RULES_CORE` in `lib/set_orch/templates.py` — remove: schema/migration ordering, CRUD test checklist, i18n namespace, layout/middleware/tailwind references. Keep: complexity S/M only, dependency ordering (infra→foundation→feature→cleanup), scope 800-1500 chars, change grouping rules, phase assignment, max_change_target. [REQ: core-planning-rules-contain-only-universal-rules]
- [x] 3.2 Update `_get_planning_rules()` in `lib/set_orch/templates.py` (line ~418) — this is the function that assembles rules, NOT `render_planning_prompt()`. After core rules, append `profile.planning_rules()` if non-empty, under a `## Project-Type Rules` header. [REQ: profile-provides-planning-rules]
- [x] 3.3 Update `_assign_cross_cutting_ownership()` in `lib/set_orch/planner.py` — replace hardcoded `_DEFAULT_CROSS_CUTTING_FILES` with `profile.cross_cutting_files()`. Add `profile` parameter to function signature. Update call site at line ~1185 to pass `profile` (thread from `enrich_plan_metadata()` or `run_planning_pipeline()` where profile is already in scope). [REQ: profile-provides-cross-cutting-file-list]

## 4. Hard Validation

- [x] 4.1 Add `max_change_target` parameter to `validate_plan()` in `lib/set_orch/planner.py` — validate `len(changes) <= max_change_target`. Error: "Plan has N changes, max allowed is M. Merge related changes." Update call site in `run_planning_pipeline()` (line ~1828) to pass `max_change_target = max_parallel * 2`. Log validation. [REQ: hard-validation-of-change-count]
- [x] 4.2 Add complexity validation to `validate_plan()` — reject `complexity not in {"S", "M"}`. Error per change: "Change '<name>' has complexity L. Split into S or M changes." [REQ: hard-validation-of-change-complexity]
- [x] 4.3 Add model validation to `validate_plan()` — reject `model not in {"opus", "sonnet"}`. Error: "Change '<name>' has invalid model '<model>'. Use 'opus' or 'sonnet'." [REQ: hard-validation-of-model-assignment]
- [x] 4.4 Add scope length validation to `validate_plan()` — reject `len(scope) > 2000`. Error: "Change '<name>' scope is N chars (max 2000). Split the change or reduce scope." [REQ: hard-validation-of-scope-length]
- [x] 4.5 Ensure `run_planning_pipeline()` passes validation errors back to LLM retry prompt — verify existing retry mechanism includes validation error messages. Log each retry reason. [REQ: hard-validation-of-change-count]

## 5. Tests

- [x] 5.1 Unit test `validate_plan()` hard checks — plan with 8 changes (max 6) → error, complexity "L" → error, model "haiku" → error, scope 2500 chars → error. Also test valid plans pass. [REQ: hard-validation-of-change-count]
- [x] 5.2 Unit test `WebProjectType.planning_rules()` — returns non-empty string containing schema/migration, CRUD, i18n keywords. [REQ: profile-provides-planning-rules]
- [x] 5.3 Unit test `WebProjectType.cross_cutting_files()` — returns list containing layout.tsx, middleware.ts, etc. [REQ: profile-provides-cross-cutting-file-list]
- [x] 5.4 Unit test `CoreProfile.planning_rules()` returns `""` and `CoreProfile.cross_cutting_files()` returns `[]`. [REQ: core-planning-rules-contain-only-universal-rules]
- [x] 5.5 Integration test: `render_planning_prompt()` with CoreProfile → no web keywords; with WebProjectType → web keywords present. [REQ: core-planning-rules-contain-only-universal-rules]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN plan has 5 changes and max=6 THEN no error [REQ: hard-validation-of-change-count, scenario: plan-within-change-limit]
- [x] AC-2: WHEN plan has 8 changes and max=6 THEN error + retry [REQ: hard-validation-of-change-count, scenario: plan-exceeds-change-limit]
- [x] AC-3: WHEN all complexity S or M THEN no error [REQ: hard-validation-of-change-complexity, scenario: valid-complexity-values]
- [x] AC-4: WHEN complexity L THEN error [REQ: hard-validation-of-change-complexity, scenario: l-complexity-rejected]
- [x] AC-5: WHEN model opus or sonnet THEN no error [REQ: hard-validation-of-model-assignment, scenario: valid-model-values]
- [x] AC-6: WHEN model haiku THEN error [REQ: hard-validation-of-model-assignment, scenario: invalid-model-rejected]
- [x] AC-7: WHEN scope 1500 chars THEN no error [REQ: hard-validation-of-scope-length, scenario: scope-within-limit]
- [x] AC-8: WHEN scope 2500 chars THEN error [REQ: hard-validation-of-scope-length, scenario: oversized-scope-rejected]
- [x] AC-9: WHEN CoreProfile THEN planning_rules returns "" [REQ: profile-provides-planning-rules, scenario: core-profile-returns-no-planning-rules]
- [x] AC-10: WHEN WebProjectType THEN planning_rules returns schema/CRUD/i18n rules [REQ: profile-provides-planning-rules, scenario: web-profile-returns-web-specific-rules]
- [x] AC-11: WHEN CoreProfile THEN cross_cutting_files returns [] [REQ: profile-provides-cross-cutting-file-list, scenario: core-profile-returns-no-cross-cutting-files]
- [x] AC-12: WHEN WebProjectType THEN cross_cutting_files returns layout.tsx etc [REQ: profile-provides-cross-cutting-file-list, scenario: web-profile-returns-web-cross-cutting-files]
- [x] AC-13: WHEN non-web project THEN prompt has no web keywords [REQ: core-planning-rules-contain-only-universal-rules, scenario: non-web-project-gets-no-web-rules]
- [x] AC-14: WHEN web project THEN prompt has core + web rules [REQ: core-planning-rules-contain-only-universal-rules, scenario: web-project-gets-full-rules]
