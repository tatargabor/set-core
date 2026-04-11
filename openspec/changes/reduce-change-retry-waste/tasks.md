# Tasks

## 1. Verify pipeline gate order swap (core)

- [x] 1.1 Read `lib/set_orch/verifier.py` lines 2960-3033 to confirm the current registration order matches the design: `build → test → [profile: e2e, lint] → scope_check → test_files → e2e_coverage → review → rules → spec_verify` [REQ: spec_verify runs before review in the pre-merge pipeline]
- [x] 1.2 Move the `review` gate registration block (currently at lines 3014-3023) to AFTER the `spec_verify` block (currently at lines 3028-3032). New order: `... → e2e_coverage → spec_verify → rules → review` [REQ: spec_verify runs before review in the pre-merge pipeline]
- [x] 1.3 Verify no other call site assumes the old order (grep for `pipeline.register` and any hardcoded gate sequencing outside the pipeline definition). Update any such reference [REQ: spec_verify runs before review in the pre-merge pipeline]
- [x] 1.4 Update the `_gate_names` list at `verifier.py:3087` if it reflects execution order: reorder to match the new pipeline (`["build", "test", "e2e", "lint", "scope_check", "test_files", "e2e_coverage", "spec_verify", "rules", "review"]`) [REQ: spec_verify runs before review in the pre-merge pipeline]
- [x] 1.5 Re-read `_execute_review_gate` (verifier.py ~2310-2428) and confirm it does NOT read `spec_verify_output` or `spec_coverage_result`. If it does, add a comment and flag in the design — but the code inspection already says it doesn't [REQ: review and spec_verify remain independent]
- [x] 1.6 Re-read `_execute_spec_verify_gate` (verifier.py ~2478-2600) and confirm it does NOT read `review_output` or `review_result` [REQ: review and spec_verify remain independent]

## 2. Pipeline order regression test (core)

- [x] 2.1 Identify an existing unit test file for verifier or pipeline (e.g. `tests/test_verifier.py`, `tests/test_pipeline.py`). If none exists, create `tests/test_verifier_gate_order.py` [REQ: Pipeline order regression test]
- [x] 2.2 Write a test that constructs a `PipelineRunner` via the verifier's registration helper with a stub profile (providing no-op `register_gates` returning e2e and lint), then asserts the ordered list of gate names equals `["build", "test", "e2e", "lint", "scope_check", "test_files", "e2e_coverage", "spec_verify", "rules", "review"]`. Skip `review` if `review_before_merge=False` [REQ: Pipeline order regression test]
- [x] 2.3 The test SHOULD NOT require a running Claude CLI or network — inject a fake `gc` (gate config) and fake `change`, and stop the pipeline before any gate actually executes (just inspect the registered names) [REQ: Pipeline order regression test]

## 3. Unify e2e_retry_limit default (core)

- [x] 3.1 Add `DEFAULT_E2E_RETRY_LIMIT = 3` as a module-level constant at the top of `lib/set_orch/engine.py`, immediately after imports and before the `Directives` dataclass [REQ: Single default constant for e2e_retry_limit, Default lowered from 5 to 3]
- [x] 3.2 Change `Directives.e2e_retry_limit` field default (currently `= 5` at `engine.py:64`) to `= DEFAULT_E2E_RETRY_LIMIT` [REQ: Single default constant for e2e_retry_limit, Default lowered from 5 to 3]
- [x] 3.3 In `lib/set_orch/merger.py`, find the fallback read (around line 1704: `state.extras.get("directives", {}).get("e2e_retry_limit", 3)`) and replace the `3` literal with an import of `DEFAULT_E2E_RETRY_LIMIT` from `engine`. Use a local import if circular-import risk exists (verify first) [REQ: Single default constant for e2e_retry_limit]
- [x] 3.4 Grep `lib/set_orch/` and `modules/` for any other `e2e_retry_limit` hardcoded defaults or literal `= 5`/`= 3` fallbacks. Replace any duplicates with the constant [REQ: Single default constant for e2e_retry_limit]
- [x] 3.5 Update the directive parsing at `engine.py:124` to use `DEFAULT_E2E_RETRY_LIMIT` in any default chain (e.g. `_int(directives.get("e2e_retry_limit"), DEFAULT_E2E_RETRY_LIMIT)`) [REQ: Explicit directive override still honored]

## 4. Web template testing conventions — cross-spec DB pollution (module)

- [x] 4.1 Read the current `modules/web/set_project_web/templates/nextjs/rules/testing-conventions.md` and find the insertion point after the existing `## Playwright Strict Mode on Repeated Elements` section (~line 325) [REQ: Cross-spec DB pollution rule forbids exact-count assertions]
- [x] 4.2 Append a new `## Cross-Spec DB Pollution — Exact Counts Forbidden` section explaining: Playwright runs specs in a single worker with SQLite, specs share the same dev.db within one run, and any test that writes rows pollutes counts seen by alphabetically-later specs [REQ: Cross-spec DB pollution rule forbids exact-count assertions]
- [x] 4.3 Include a WRONG code block: a storefront listing test that asserts `await expect(cards).toHaveCount(6)` where 6 is the seed count [REQ: Cross-spec DB pollution rule forbids exact-count assertions]
- [x] 4.4 Include a CORRECT code block: the same test using `await expect(cards).toHaveCount({ min: 6 })` with a comment explaining the `min` form. Also show an alternative pattern using `.filter({ hasText: "known-seed-name" })` to count only specific rows [REQ: Cross-spec DB pollution rule forbids exact-count assertions]
- [x] 4.5 Add an "Applicability" paragraph: forbid exact counts whenever the counted entity type is also written by any other spec in the same suite [REQ: Cross-spec DB pollution rule forbids exact-count assertions]

## 5. Web template testing conventions — getByLabel prefix ambiguity (module)

- [x] 5.1 Append a new `## getByLabel Prefix Ambiguity — Require exact: true` section after the cross-spec pollution section [REQ: getByLabel prefix-ambiguity rule requires exact: true]
- [x] 5.2 Explain that `getByLabel` defaults to substring matching in Playwright, so labels sharing a prefix ("Description" / "Short Description", "Name" / "Display Name", "Price" / "Sale Price") cause strict-mode violations [REQ: getByLabel prefix-ambiguity rule requires exact: true]
- [x] 5.3 Include a WRONG code block using `getByLabel("Description")` that matches both labels and throws [REQ: getByLabel prefix-ambiguity rule requires exact: true]
- [x] 5.4 Include a CORRECT code block using `getByLabel("Description", { exact: true })` [REQ: getByLabel prefix-ambiguity rule requires exact: true]
- [x] 5.5 Add an "Applicability" paragraph: use `{ exact: true }` on every `getByLabel` call whose text is a prefix or suffix of another label on the same page [REQ: getByLabel prefix-ambiguity rule requires exact: true]

## 6. Web template testing conventions — toHaveURL regex (module)

- [x] 6.1 Append a new `## toHaveURL Regex — Exclude Intermediate Routes` section after the prefix-ambiguity section [REQ: toHaveURL regex exclusion rule]
- [x] 6.2 Explain that `toHaveURL(/\/admin/)` matches `/admin/login` immediately because Playwright's URL regex is a substring match, causing the test to proceed before the post-login redirect lands [REQ: toHaveURL regex exclusion rule]
- [x] 6.3 Include a WRONG code block: `await expect(page).toHaveURL(/\/admin/)` after a login form submit [REQ: toHaveURL regex exclusion rule]
- [x] 6.4 Include TWO CORRECT code blocks: one with negative lookahead `await expect(page).toHaveURL(/\/admin(?!\/login)/)`, one anchoring to a specific path `await expect(page).toHaveURL(/\/admin\/dashboard/)` [REQ: toHaveURL regex exclusion rule]
- [x] 6.5 Add an "Applicability" paragraph: use exclusion or specific-path patterns whenever the target path has a login or setup sub-route that shares the same prefix [REQ: toHaveURL regex exclusion rule]

## 7. Verify no other file references the old gate order or old retry default

- [x] 7.1 Grep the codebase for `"review"` followed by `"spec_verify"` or ordered lists of gate names to catch documentation that mentions the old order (`docs/`, `README`, `CLAUDE.md` files) [REQ: spec_verify runs before review in the pre-merge pipeline]
- [x] 7.2 Update any documentation that describes the gate order
- [x] 7.3 Grep for `e2e_retry_limit` in `docs/`, `templates/`, and consumer-facing files to catch documentation that mentions the old default of 5
- [x] 7.4 Update those docs to either reference `DEFAULT_E2E_RETRY_LIMIT` or state the new default (3)

## 8. Smoke test the change end-to-end (manual, post-implementation)

- [ ] 8.1 Build and install the modified set-core package in a throwaway project dir [REQ: spec_verify runs before review in the pre-merge pipeline]
- [ ] 8.2 Kick off a tiny orchestration (1-2 changes) against a trivial spec and confirm the VERIFY_GATE events show `spec_verify` timing before `review` timing in the emitted `gate_ms` map [REQ: spec_verify runs before review in the pre-merge pipeline]
- [ ] 8.3 Manually trigger a spec-gap scenario (have an agent skip persisting a required field) and confirm `spec_verify` fires first and stops the pipeline before `review` would have run [REQ: spec_verify runs before review in the pre-merge pipeline]
- [ ] 8.4 Confirm the new web template rules render in the agent prompt when a Playwright test file is in the change diff

## 9. Update the verifier regression rule in .claude/rules (optional, core)

- [x] 9.1 If `.claude/rules/` has a rule file covering verifier gate order, update it. If not, skip — the regression test from task 2 is the authoritative guard
