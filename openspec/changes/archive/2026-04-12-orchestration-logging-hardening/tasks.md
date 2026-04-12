## 1. Dispatcher logging

- [x] 1.1 Add dispatch summary INFO log at end of `dispatch_change()` — single line: `INFO: Dispatched {change}: requirements={n}, test_plan_entries={n}, digest_dir={'set'|'empty'}, design={'yes'|'no'}, retry={n}`
- [x] 1.2 `[ANOMALY]` WARNING if feature change dispatched with 0 requirements: `WARNING: [ANOMALY] Feature change {name} dispatched with 0 requirements — agent won't get Required Tests`
- [x] 1.3 `[ANOMALY]` WARNING if digest_dir provided but test_plan_entries is 0 for a change with requirements: `WARNING: [ANOMALY] {name} has {n} requirements but 0 test plan entries — test-plan.json may not match`
- [x] 1.4 WARNING in `_build_input_content()` if scope E2E post-processing finds no E2E pattern to replace (test plan exists but scope has no E2E line): just DEBUG, not warning — this is normal for non-feature scopes.
- [x] 1.5 INFO log for e2e-manifest.json write: `INFO: Wrote e2e-manifest.json for {change}: {n} spec files, {n} requirements`

## 2. Merger logging

- [x] 2.1 Add gate pipeline summary INFO at end of `_run_integration_gates()`: `INFO: Gate pipeline for {change}: build={result}({ms}ms) test={result}({ms}ms) e2e_smoke={result}({ms}ms) e2e_own={result}({ms}ms) coverage={result}({pct}%) — {PASSED|FAILED}`
- [x] 2.2 WARNING in `_collect_test_artifacts()` if profile is NullProfile: `WARNING: [ANOMALY] NullProfile for test artifact collection in {wt_path} — project-type detection failed`
- [x] 2.3 WARNING if coverage check skipped for feature change with requirements: `WARNING: Coverage check skipped for feature {name} — {reason}` (reason: no test-plan, threshold=0, etc.)
- [x] 2.4 INFO log for two-phase E2E: `INFO: E2E two-phase: {n} own specs, {n} inherited specs, smoke={n} tests`

## 3. Engine logging

- [x] 3.1 `[ANOMALY]` WARNING if agent completed with 0 commits: `WARNING: [ANOMALY] Agent for {change} completed but 0 commits on branch — possible false-done`
- [x] 3.2 `[ANOMALY]` WARNING if E2E gate passed with 0 test files: `WARNING: [ANOMALY] E2E gate passed for {change} but 0 spec files found — tests may be missing`
- [x] 3.3 WARNING in `_dispatch_ready_safe()` if digest_dir resolves to empty: `WARNING: digest_dir is empty for dispatch — agents won't get Required Tests section`
- [x] 3.4 INFO for stall recovery: `INFO: Recovering stalled {change} — stalled for {n}s, reason={reason}`
- [x] 3.5 INFO for coverage-failed recovery: `INFO: Recovering coverage-failed {change} — redispatching agent for missing tests`

## 4. Profile loader logging

- [x] 4.1 In `load_profile()` (`profile_loader.py`): if `project-type.yaml` exists but type_name is empty or invalid, log `WARNING: [ANOMALY] project-type.yaml found but type '{type_name}' unknown — using NullProfile (no project-specific knowledge)`
- [x] 4.2 If `project-type.yaml` doesn't exist, log `DEBUG: No project-type.yaml — using NullProfile`
- [x] 4.3 If profile loaded successfully, log `DEBUG: Loaded profile {type(profile).__name__} from {path}` (already existed as INFO via entry_points/direct import/built-in module paths)

## 5. Planner logging

- [x] 5.1 INFO for test plan context injection: `INFO: Injecting {n} test plan entries for domain {domain} into planner prompt`
- [x] 5.2 WARNING if test load validation finds >40 tests: `WARNING: Change {name} has {n} required tests ({m} REQs) — consider splitting`
- [x] 5.3 INFO for plan validation summary: `INFO: Plan validated: {n} changes, {n} warnings, {n} errors`

## 6. Verifier/state logging

- [x] 6.1 WARNING in `_append_review_finding()` if write fails: `WARNING: Review finding lost — cannot write to {path}: {error}`
- [x] 6.2 DEBUG in `Change.from_dict()` if unknown fields stored in extras: `DEBUG: Change {name}: {n} unknown fields stored in extras`
