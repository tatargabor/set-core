## Fix A — Required Tests Injection (dispatcher.py)

- [x] A.1 Broaden the scope E2E regex at L1058 to match common narrative patterns: `E2E tests/e2e/...`, `E2E:...`, `Tests:...`, and multi-line `E2E\ntests/e2e/...` blocks. When matched, replace with Required Tests pointer.
- [x] A.2 When no regex match but `_test_plan_entries` is non-empty, strip any remaining `tests/e2e/*.spec.ts` file references from the scope to prevent conflicting guidance.
- [x] A.3 Add INFO log when Required Tests section is appended (currently only logs when it's NOT appended): `"Required Tests injected for %s: %d entries from test plan"`.

## Fix B — Per-Change Coverage (merger.py)

- [x] B.1 In `_parse_test_coverage_if_applicable` (L2053-2086): use `change.requirements` as the REQ-ID set when `change.requirements` is non-empty. Only fall back to `digest_req_ids` when `change.requirements` is empty or when `change_type == "acceptance-tests"`.
- [x] B.2 Log which REQ set is being used: `"Coverage parsing for %s: using %d per-change reqs (not %d digest reqs)"`.
- [x] B.3 In `build_test_coverage` call (L2089-2095): pass `change.requirements` as `digest_req_ids` when available, so `covered_reqs` and `uncovered_reqs` are relative to the change's own scope.
- [x] B.4 Verify the coverage gate (L1282-1362) already uses per-change `_change_reqs` — confirm it does, add a comment noting the consistency.

## Fix C — REQ-ID Enforcement (rules/templates)

- [x] C.1 Add REQ-ID naming rule to `modules/web/set_project_web/planning_rules.txt`: "Every E2E test block MUST include its REQ-XXX-NNN prefix in the test name for coverage tracking."
- [x] C.2 Add or update `templates/core/rules/set-testing.md` with REQ-ID naming requirement and example format. If the file doesn't exist, create it.
- [x] C.3 Verify that the existing Required Tests section in dispatcher.py (L1163-1167) already instructs agents to use REQ-ID prefix — confirm it does.
