## 1. Phase 1 brief prompt update

- [x] 1.1 Edit `render_brief_prompt` in `lib/set_orch/templates.py`. Insert a "DOMAIN ENUMERATION RULES" block between the existing `## Task` section and the `## Output` schema. Block content: domain_priorities MUST contain feature/code domains only; MUST NOT contain `testing`, `tests`, `e2e`, `playwright`, `vitest`, `qa`, `validation`. Test requirements belong to the feature domain that owns the code under test. The only allowed test-related cross-cutting change is `test-infrastructure-setup` [REQ: phase-1-brief-prompt-forbids-test-only-domains]
- [x] 1.2 Add a unit test asserting that `render_brief_prompt(...)` output contains `"DOMAIN ENUMERATION RULES"` AND each forbidden token AND `"test-infrastructure-setup"` AND the feature-domain ownership instruction [REQ: phase-1-brief-prompt-forbids-test-only-domains]

## 2. Phase 2 per-domain prompt update

- [x] 2.1 Edit `render_domain_decompose_prompt` in `lib/set_orch/templates.py`. Add to the existing `## Constraints` block one new mandatory bullet: each change with user-facing UI or HTTP routes MUST list at least one `tests/e2e/<feature>.spec.ts` path in its `spec_files`, and the change's `scope` text MUST mention that spec file path [REQ: phase-2-per-domain-prompt-requires-e2e-ownership-in-feature-changes]
- [x] 2.2 Add a unit test asserting that `render_domain_decompose_prompt(...)` output contains the e2e ownership instruction with the path pattern `tests/e2e/<feature>.spec.ts` [REQ: phase-2-per-domain-prompt-requires-e2e-ownership-in-feature-changes]

## 3. Phase 3 merge prompt update

- [x] 3.1 Edit `render_merge_prompt` in `lib/set_orch/templates.py`. Add to the existing `## Rules` block one rule: any incoming change name matching `^(playwright|e2e|vitest)-` AND not exactly `test-infrastructure-setup` MUST be refolded — its `requirements`, `spec_files`, and `also_affects_reqs` MUST be merged into the corresponding feature change [REQ: phase-3-merge-prompt-refolds-standalone-test-changes]
- [x] 3.2 Add a unit test asserting `render_merge_prompt(...)` output contains the refold rule and names `test-infrastructure-setup` as the singleton exception [REQ: phase-3-merge-prompt-refolds-standalone-test-changes]

## 4. Post-Phase-3 fail-fast guard

- [x] 4.1 In `lib/set_orch/planner.py`, define a module-level constant `_TEST_CHANGE_NAME_PREFIXES_RE = re.compile(r"^(playwright|e2e|vitest)-")` and `_TEST_INFRA_CHANGE_NAME = "test-infrastructure-setup"` near the existing `DOMAIN_PARALLEL_MIN_REQS` constant [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]
- [x] 4.2 Implement `_assert_no_standalone_test_changes(plan_data: dict) -> None` that iterates `plan_data.get("changes", [])`, applies the regex to each change's `name`, and raises `RuntimeError("decompose-test-bundling violation: change '<name>' is a standalone test change. Tests must bundle with their feature change. See openspec/changes/decompose-tests-bundled-with-features/.")` if a violation is found [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]
- [x] 4.3 Call `_assert_no_standalone_test_changes(plan_data)` in `_try_domain_parallel_decompose` immediately after `decompose_merge` returns and the plan is parsed, BEFORE persistence or any further processing. Do NOT call it on the flat decompose path [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes, REQ: flat-decompose-path-is-unaffected]
- [x] 4.4 Unit test: feed `_assert_no_standalone_test_changes` a plan containing `playwright-smoke-tests` → asserts `RuntimeError` raised with message naming the change and the capability [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]
- [x] 4.5 Unit test: feed a plan containing only `test-infrastructure-setup` (singleton) → asserts no error [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]
- [x] 4.6 Unit test: feed a plan with feature changes `content-home-page`, `command-palette` (no test prefixes) → asserts no error [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]
- [x] 4.7 Unit test: feed a mixed plan containing `vitest-suite` AND `auth-login` → asserts `RuntimeError` naming `vitest-suite` [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]
- [x] 4.8 Unit test: feed a plan containing `test-infrastructure-setup` AND `playwright-extra-suite` → asserts `RuntimeError` naming `playwright-extra-suite` (the infra exception is exact-match, not prefix) [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]

## 5. Validation procedure (3 scaffolds)

- [x] 5.1 Document a procedure (in this tasks.md) that runs `set-orch-core digest run` for `tests/e2e/scaffolds/{micro-web,minishop,craftbrew}` (after `--digest-cache-clear` once at start) and captures the resulting `orchestration-plan.json` for each [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]
- [ ] 5.2 For each scaffold's plan, assert that NO change name matches `^(playwright|e2e|vitest)-` other than `test-infrastructure-setup` (live LLM run; deferred to next E2E session) [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]
- [ ] 5.3 For each scaffold's plan, assert that every change with `change_type=feature` whose scope mentions UI/route work also mentions a `tests/e2e/<feature>.spec.ts` path in its scope text (live LLM run; deferred) [REQ: phase-2-per-domain-prompt-requires-e2e-ownership-in-feature-changes]

## 6. Docs

- [ ] 6.1 Update release notes / changelog (or `docs/release/` notes if present) with a one-line entry: "Domain-parallel decompose now bundles e2e tests with their feature changes (regression fix). In-flight `playwright-*` plans on disk finish under their original plan; new plans use the bundled pipeline." [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes]

## Acceptance Criteria (from spec scenarios)

### Capability: decompose-test-bundling

- [ ] AC-1: WHEN the planner calls `render_brief_prompt(...)` for any spec THEN the rendered prompt contains "DOMAIN ENUMERATION RULES" AND lists each forbidden token AND names `test-infrastructure-setup` [REQ: phase-1-brief-prompt-forbids-test-only-domains, scenario: phase-1-prompt-enumerates-the-forbidden-tokens]
- [ ] AC-2: WHEN the rendered Phase 1 prompt is inspected THEN it explicitly states test requirements belong to the feature domain that owns the code under test [REQ: phase-1-brief-prompt-forbids-test-only-domains, scenario: phase-1-prompt-instructs-feature-domain-test-ownership]
- [ ] AC-3: WHEN `render_domain_decompose_prompt(...)` is called THEN its `## Constraints` section names the e2e ownership constraint AND the `tests/e2e/<feature>.spec.ts` path pattern [REQ: phase-2-per-domain-prompt-requires-e2e-ownership-in-feature-changes, scenario: phase-2-prompt-names-the-e2e-ownership-constraint]
- [ ] AC-4: WHEN `render_merge_prompt(...)` is called THEN its `## Rules` section names the refold rule AND `test-infrastructure-setup` as the singleton exception [REQ: phase-3-merge-prompt-refolds-standalone-test-changes, scenario: phase-3-prompt-names-the-refold-rule]
- [ ] AC-5: WHEN Phase 3 returns a plan containing `playwright-smoke-tests` THEN the post-merge guard raises `RuntimeError` naming the change AND `decompose-test-bundling`, AND the plan is not persisted [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes, scenario: standalone-playwright-change-triggers-fail-fast]
- [ ] AC-6: WHEN Phase 3 returns a plan with only `test-infrastructure-setup` THEN the guard raises no error AND persistence proceeds [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes, scenario: singleton-test-infrastructure-setup-is-allowed]
- [ ] AC-7: WHEN Phase 3 returns a plan with feature changes that each carry their own `tests/e2e/<feature>.spec.ts` THEN the guard raises no error [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes, scenario: feature-changes-with-bundled-e2e-specs-pass]
- [ ] AC-8: WHEN Phase 3 returns a plan containing `vitest-validation-suite` AND `auth-login` THEN the guard raises `RuntimeError` naming `vitest-validation-suite` [REQ: post-phase-3-fail-fast-guard-rejects-standalone-test-changes, scenario: mixed-prefix-violation-triggers-fail-fast]
- [ ] AC-9: WHEN a small spec or `force_strategy: flat` runs THEN the planner uses `render_planning_prompt` unchanged AND the post-Phase-3 guard does NOT execute [REQ: flat-decompose-path-is-unaffected, scenario: flat-planner-output-unchanged]
