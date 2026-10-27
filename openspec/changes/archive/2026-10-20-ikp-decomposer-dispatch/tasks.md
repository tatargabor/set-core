## 1. Decomposer IKP Context

- [x] 1.1 Add `ikp_context: str = ""` parameter to `build_decomposition_context()` in `lib/set_orch/planner.py` and include it in the returned context dict [REQ: ikp-context-in-decomposition-prompt]
- [x] 1.2 In `run_planning_pipeline()`, call `ikp_bridge.has_ikp_pipeline()` and if active, call `ikp_bridge.get_context_for_phase("decompose", ...)` to build the IKP context string [REQ: ikp-context-in-decomposition-prompt]
- [x] 1.3 Add IKP section to the planning prompt template (in `templates.render_planning_prompt()` or equivalent) — render `ikp_context` as `## Integration Knowledge (IKP)` section [REQ: ikp-context-in-decomposition-prompt]

## 2. Planner Output Schema

- [x] 2.1 Add `ikp_packs` instruction to the planner prompt — tell the planner to assign relevant pack names from the IKP section to each change's output [REQ: planner-assigns-ikp-packs-per-change]
- [x] 2.2 In `_enrich_change_metadata()` (or equivalent plan parsing), preserve `ikp_packs` field from planner output, defaulting to `[]` if absent [REQ: planner-assigns-ikp-packs-per-change]
- [x] 2.3 Implement fallback keyword matching in plan enrichment — scan scope text for pack names from `.ikp.yaml` when planner didn't assign packs [REQ: fallback-pack-assignment]

## 3. Dispatcher IKP Injection

- [x] 3.1 In `dispatch_change()`, read `ikp_packs` from change metadata after design deployment [REQ: dispatcher-injects-ikp-rules-into-worktree]
- [x] 3.2 Call `ikp_bridge.inject_rules_for_change()` with the change's `ikp_packs`, language from IkpConfig, and worktree path [REQ: dispatcher-injects-ikp-rules-into-worktree]
- [x] 3.3 Add `## Integration Packs (IKP)` section to `_build_input_content()` — brief per-pack summary with capabilities, env vars, pitfalls, and reference to `.claude/rules/ikp-*.md` [REQ: ikp-summary-in-input-md]

## 4. Category Resolver

- [x] 4.1 Add IKP signal layer to `resolve_change_categories()` in `lib/set_orch/category_resolver.py` — add `"integration"` when `ikp_packs` is non-empty [REQ: resolver-runs-six-deterministic-detection-layers-per-change]
- [x] 4.2 Add `"integration"` to WebProjectType's `category_taxonomy()` return value in `modules/web/set_project_web/base.py` [REQ: resolver-runs-six-deterministic-detection-layers-per-change]
- [x] 4.3 Pass `ikp_packs` (or change metadata) to `resolve_change_categories()` — add parameter to function signature [REQ: resolver-runs-six-deterministic-detection-layers-per-change]

## 5. Verify Gate

- [x] 5.1 In `review_change()` in `lib/set_orch/verifier.py`, check for `ikp_packs` in change metadata [REQ: llm-code-review]
- [x] 5.2 If packs present and IKP pipeline active, call `ikp_bridge.get_context_for_phase("verify", ...)` and append L4 testing context to the review prompt [REQ: llm-code-review]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `has_ikp_pipeline()` returns True and project declares 3 packs THEN `build_decomposition_context()` includes `ikp_context` with per-pack sections [REQ: ikp-context-in-decomposition-prompt, scenario: project-with-ikp-packs]
- [x] AC-2: WHEN `has_ikp_pipeline()` returns False THEN `ikp_context` is empty and prompt has no IKP section [REQ: ikp-context-in-decomposition-prompt, scenario: project-without-ikp]
- [x] AC-3: WHEN planner creates a change for "Billingo API integration" THEN output includes `"ikp_packs": ["billingo"]` [REQ: planner-assigns-ikp-packs-per-change, scenario: integration-change]
- [x] AC-4: WHEN planner creates "Prisma schema" change THEN `ikp_packs` is empty or omitted [REQ: planner-assigns-ikp-packs-per-change, scenario: non-integration-change]
- [x] AC-5: WHEN planner omits `ikp_packs` THEN enrichment defaults to `[]` [REQ: planner-assigns-ikp-packs-per-change, scenario: planner-omits-ikp-packs]
- [x] AC-6: WHEN change has empty `ikp_packs` but scope contains "billingo" and it's in `.ikp.yaml` THEN enrichment sets `ikp_packs: ["billingo"]` with warning [REQ: fallback-pack-assignment, scenario: keyword-match-fallback]
- [x] AC-7: WHEN dispatching change with `ikp_packs: ["billingo"]` and IKP active THEN `<wt>/.claude/rules/ikp-billingo.md` is created [REQ: dispatcher-injects-ikp-rules-into-worktree, scenario: change-with-ikp-packs]
- [x] AC-8: WHEN dispatching change with no `ikp_packs` THEN IKP injection is skipped entirely [REQ: dispatcher-injects-ikp-rules-into-worktree, scenario: change-without-ikp-packs]
- [x] AC-9: WHEN change has `ikp_packs` THEN input.md contains `## Integration Packs (IKP)` section with capabilities, env vars, and pitfalls [REQ: ikp-summary-in-input-md, scenario: ikp-section-content]
- [x] AC-10: WHEN change has `ikp_packs: ["billingo"]` THEN `"integration"` is added to resolved categories [REQ: resolver-runs-six-deterministic-detection-layers-per-change, scenario: change-with-ikp-packs]
- [x] AC-11: WHEN reviewing change with `ikp_packs` and IKP active THEN review prompt includes L4 testing context [REQ: llm-code-review, scenario: review-with-ikp-testing-context]
