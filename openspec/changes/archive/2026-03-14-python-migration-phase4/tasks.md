## 1. Data Types and Module Setup

- [x] 1.1 Create `lib/set_orch/planner.py` with dataclasses: `ValidationResult` (errors: list[str], warnings: list[str]), `ScopeOverlap` (name_a: str, name_b: str, similarity: int), `TestInfra` (framework: str, config_exists: bool, test_file_count: int, has_helpers: bool, test_command: str), `TriageStatus` (status: str, count: int)
- [x] 1.2 Add imports from existing modules: `config.py` (find_input, resolve_directives, brief_hash, load_config_file), `state.py` (topological_sort), `templates.py` (render_planning_prompt), `events.py` (EventBus)

## 2. Plan Validation

- [x] 2.1 Implement `validate_plan(plan_path, digest_dir=None)` → `ValidationResult` — JSON structure check, required fields (plan_version, brief_hash, changes), change-level required fields
- [x] 2.2 Add kebab-case name validation: regex `^[a-z][a-z0-9-]*$` on all change names
- [x] 2.3 Add depends_on reference validation: all targets must exist as change names in the plan
- [x] 2.4 Add circular dependency detection via `topological_sort` from state.py
- [x] 2.5 Add digest-mode requirement coverage validation: check requirements and also_affects_reqs against requirements.json IDs, also_affects_reqs primary owner check

## 3. Scope Overlap Detection

- [x] 3.1 Implement `_extract_scope_keywords(scope_text)` → set[str] — extract lowercase 3+ char words, deduplicate
- [x] 3.2 Implement `check_scope_overlap(plan_path, state_path=None, pk_path=None)` → list[ScopeOverlap] — pairwise Jaccard similarity using Python set intersection/union, threshold >= 40%
- [x] 3.3 Add overlap check against active worktree changes from state file (status running/dispatched/done)
- [x] 3.4 Add cross-cutting file hazard detection from project-knowledge.yaml (conditional PyYAML import)

## 4. Test Infrastructure Detection

- [x] 4.1 Implement `detect_test_infra(project_dir)` → `TestInfra` — scan for vitest.config.*, jest.config.*, pytest in pyproject.toml, mocha in package.json devDependencies
- [x] 4.2 Implement `_auto_detect_test_command(project_dir)` → str — detect package manager from lockfile (pnpm/yarn/bun/npm), find test script (test/test:unit/test:ci)
- [x] 4.3 Add test file counting (*.test.*, *.spec.*, test_*.py excluding node_modules/.git) and helper directory detection (src/test, __tests__, test, tests)

## 5. Triage Gate and Spec Summarization

- [x] 5.1 Implement `check_triage_gate(digest_dir, auto_defer=False)` → `TriageStatus` — read ambiguities.json and triage.md, evaluate gate status (no_ambiguities/needs_triage/has_untriaged/has_fixes/passed)
- [x] 5.2 Implement `summarize_spec(spec_path, phase_hint="", model="haiku")` — estimate tokens (words × 1.3), call Claude via subprocess_utils.run_claude if over threshold, fallback to truncation on failure
- [x] 5.3 Implement `estimate_tokens(file_path)` → int — word count × 1.3

## 6. Decomposition Context Assembly

- [x] 6.1 Implement `build_decomposition_context(input_mode, input_path, ...)` → dict — assemble context for template rendering: existing specs, active changes, test infra, memory, design, project knowledge, requirements
- [x] 6.2 Add digest-mode context: conventions, data model, execution hints, domain summaries, compact requirements, dependencies, deferred ambiguities, coverage info
- [x] 6.3 Add project-knowledge.yaml cross-cutting files context (conditional PyYAML)
- [x] 6.4 Add requirements directory scanning (wt/requirements/*.yaml with status captured/planned)

## 7. Plan Metadata and Replan

- [x] 7.1 Implement `enrich_plan_metadata(plan_data, hash, input_mode, input_path, plan_version=1, replan_cycle=None)` → dict — add plan_version, brief_hash, created_at, input_mode, input_path, input_hash, plan_phase, plan_method
- [x] 7.2 Add replan depends_on stripping: remove depends_on references to completed changes from prior cycles
- [x] 7.3 Implement `collect_replan_context(state_path)` → dict — gather completed names, roadmap items, file lists (via git log), E2E failure context

## 8. CLI Bridge

- [x] 8.1 Add `plan` subcommand group to `cli.py` with subcommands: validate, detect-test-infra, check-triage, check-scope-overlap, build-context, enrich-metadata, summarize-spec, replan-context
- [x] 8.2 Implement `plan validate --plan-file <path> [--digest-dir <path>]` — output JSON with errors/warnings
- [x] 8.3 Implement `plan detect-test-infra [--project-dir <path>]` — output TestInfra as JSON
- [x] 8.4 Implement `plan check-triage --digest-dir <path> [--auto-defer]` — output status string
- [x] 8.5 Implement `plan check-scope-overlap --plan-file <path> [--state-file <path>] [--pk-file <path>]` — output warnings JSON
- [x] 8.6 Implement `plan build-context --input-file <json>` — output rendered planning prompt
- [x] 8.7 Implement `plan enrich-metadata --plan-file <path> --hash <str> --input-mode <str> --input-path <path> [--replan-cycle <int>] [--state-file <path>]` — write enriched plan
- [x] 8.8 Implement `plan summarize-spec --spec-file <path> [--phase-hint <str>] [--model <str>]` — output summary
- [x] 8.9 Implement `plan replan-context --state-file <path>` — output replan context JSON

## 9. Bash Wrapper Migration

- [x] 9.1 Replace `estimate_tokens()` in planner.sh with `set-orch-core plan` call or inline (trivial function)
- [x] 9.2 Replace `summarize_spec()` in planner.sh with `set-orch-core plan summarize-spec` wrapper
- [x] 9.3 Replace `detect_test_infra()` and `auto_detect_test_command()` in planner.sh with `set-orch-core plan detect-test-infra` wrapper
- [x] 9.4 Replace `validate_plan()` in planner.sh with `set-orch-core plan validate` wrapper
- [x] 9.5 Replace `check_scope_overlap()` in planner.sh with `set-orch-core plan check-scope-overlap` wrapper
- [x] 9.6 Replace `check_triage_gate()` in planner.sh with `set-orch-core plan check-triage` wrapper
- [x] 9.7 Replace decomposition context assembly block in `cmd_plan()` (lines 638-963) with `set-orch-core plan build-context` wrapper
- [x] 9.8 Replace plan metadata enrichment block in `cmd_plan()` (lines 1049-1092) with `set-orch-core plan enrich-metadata` wrapper
- [x] 9.9 Replace replan context collection in `auto_replan_cycle()` (lines 1280-1343) with `set-orch-core plan replan-context` wrapper
- [x] 9.10 Add "Migrated to: planner.py" comments to all replaced function bodies in planner.sh

## 10. Tests

- [x] 10.1 Add tests for `validate_plan()` — valid plan, invalid JSON, missing fields, bad names, missing deps, circular deps
- [x] 10.2 Add tests for `check_scope_overlap()` — no overlap, high overlap, active change overlap, cross-cutting hazard, insufficient keywords skip
- [x] 10.3 Add tests for `detect_test_infra()` — vitest project, pytest project, no infra, test command detection
- [x] 10.4 Add tests for `check_triage_gate()` — all 5 return states (no_ambiguities, needs_triage, has_untriaged, has_fixes, passed), auto-defer mode
- [x] 10.5 Add tests for `enrich_plan_metadata()` — initial plan, replan with depends_on stripping
- [x] 10.6 Add tests for `build_decomposition_context()` — brief mode, digest mode, with/without optional contexts
- [x] 10.7 Verify end-to-end: bash wrapper → CLI → Python → identical output to original bash functions
