# Design: Block Integration E2E Smoke Failures

## Context

The merger's integration e2e gate (`lib/set_orch/merger.py:1206-1295`) is the last safety check before a merge lands on main. It uses a two-phase strategy:

1. **Smoke phase**: run the first test from each *inherited* (not-owned-by-this-change) spec file, using the profile's `e2e_smoke_command` helper. The intent is to detect *cross-change contamination* — when the merging change's own tests pollute shared state (DB, cookies, cache) in a way that breaks a sibling change's tests.
2. **Own-test phase**: run the merging change's own spec files, scoped via `profile.e2e_scoped_command`. This is the change's own correctness check.

Historically, the smoke phase was made non-blocking because of a principled concern: "change A should not fail because of a test that change B's team wrote and change B's team is responsible for." In a multi-team scenario with weak coupling between changes, that stance is defensible — change A didn't write the smoke test and cannot reasonably be expected to fix it.

**But the observed behavior in single-team orchestration runs is the opposite.** When one team owns all the changes, a smoke failure is always a bug in the current change (new writes to shared state) or a bug in the sibling (brittle assertions). Either way, the change that surfaces the failure should block and the agent should fix the root cause immediately — not be allowed to merge garbage into main and discover it later when a different retry cycle happens to run the broken test.

Reading the current code (`merger.py:1262-1274`):

```python
if smoke_result.exit_code == 0:
    ...
    update_change_field(state_file, change_name, "smoke_e2e_result", "pass")
else:
    _smoke_failed = True
    logger.warning(
        "Integration gate: e2e smoke FAILED for %s (non-blocking, %dms) — "
        "inherited tests failed, regression possible",
        change_name, _s1e,
    )
    update_change_field(state_file, change_name, "smoke_e2e_result", "fail")
    if event_bus:
        event_bus.emit("VERIFY_GATE", ...)
    # Non-blocking: continue to Phase 2
```

The `# Non-blocking: continue to Phase 2` comment is explicit — smoke failure does NOT stop the gate. Phase 2 still runs. If Phase 2 passes, the merge proceeds with `_smoke_failed = True` dangling, only surfaced in the agent retry context if Phase 2 later fails (`merger.py:1354-1358`).

## Goals / Non-Goals

**Goals:**
- Default behavior: smoke phase failure blocks the merge and triggers a redispatch, with retry context that points the agent at the failing sibling spec files.
- Preserve escape hatch: an explicit directive flag lets operators opt out (multi-team, weak-coupling, or permissive CI setups).
- No change to Phase 2 logic — own-test failures still handle redispatch via the existing path.

**Non-Goals:**
- Changing which tests count as "smoke". The profile's `e2e_smoke_command` + `extract_first_test_name` logic remains as-is.
- Adding per-test smoke selection (e.g. only `@SMOKE` tagged tests). That is a deeper profile design question.
- Automatic "fix the sibling" logic. The retry context points at the sibling, but the agent's job is to fix the pollution source in the current change.
- Introducing a second redispatch path specifically for smoke. The existing redispatch logic (`merger.py:1336-1380`) already handles `integration-e2e-failed` changes — smoke failures reuse it.

## Decisions

### 1. Smoke failure sets `integration-e2e-failed` and redispatches via the existing path

**Choice:** When smoke fails AND `integration_smoke_blocking` is `true`, the merger:
1. Persists the smoke output to `integration_e2e_output` with a header explaining it came from the smoke phase
2. Sets `change.status = "integration-e2e-failed"`
3. Builds a retry context via `_build_gate_retry_context` enriched with a smoke-specific preamble ("Note: this failure came from smoke tests — tests owned by a sibling change whose correctness you are now affecting")
4. Returns from `_run_integration_gates` with `False`
5. Skips Phase 2 entirely (no point running own tests when the merged state is known-bad)

**Why reuse the existing redispatch path?** The downstream logic (`merger.py:1710-1720`) already recognizes `integration-e2e-failed` and routes the change to redispatch. Adding a second path for smoke would duplicate counter logic (`integration_e2e_retry_count`), event emission, and retry-limit enforcement. The existing path is tested and works.

**Why skip Phase 2 on smoke fail?** Because the merged state is already broken. Running the change's own tests on that state gives false information — either they pass (misleading: "change is fine") or fail (not the right signal: the cause is the sibling regression, not the change itself). The retry context should direct the agent at the sibling regression, not a combination of both.

### 2. Directive flag `integration_smoke_blocking` defaults to `True`

**Choice:** Add `integration_smoke_blocking: bool = True` to `Directives` in `engine.py:80` area. Parse via `_bool` in `parse_directives`. The merger reads the directive from `state.extras["directives"]` at `_run_integration_gates` entry.

**Why True?** The observed-harm case (orchestration runs silently merging broken state) is far more common than the preserved-escape case (multi-team permissive setup). Changing the default is the fix; the opt-out preserves the old behavior for the minority.

**Why a directive and not a hard-coded default?** Operators of mature projects with known-flaky smoke tests need an escape hatch until they triage those tests. Removing the flag entirely would force them to upgrade gate-behavior on a deploy-and-hope basis.

### 3. Retry context enrichment

**Choice:** The smoke-failure retry context includes:
- A one-line explanation: "Integration smoke tests failed. These tests belong to sibling changes that are already merged on main. Your change is likely polluting shared state (DB rows, `.next/` cache, session cookies) in a way that breaks them."
- The failing sibling spec file names (from `inherited_specs`)
- The first ~1500 characters of the smoke run output (via `smart_truncate_structured` — same helper as other gate outputs)
- A hint: "Fix: ensure your tests clean up with `test.afterEach`, use unique names per test (see `testing-conventions.md`), and avoid writing to shared tables without cleanup."

**Why include the sibling spec names in the retry context?** The agent reads the `inherited_specs` list and can open those files to understand what the sibling tests are asserting. Without that hint, the agent sees "smoke fail" and has no starting point.

**Why not include the full Playwright output?** The smoke output is already captured in `smoke_e2e_output` state field and truncated via `smart_truncate_structured` by the gate_runner. Duplicating it in the retry context would bloat the prompt. The first 1500 chars are enough to show the primary failure.

## Risks / Trade-offs

- **[Risk] Flaky smoke tests now block merges.** Mitigation: the baseline comparison in the wt-e2e gate already filters `pre-existing` failures out of `wt_failures`. A smoke test that fails intermittently on main has its failure ID in the baseline and is treated as pre-existing. The blocking path only fires for NEW failures (tests that pass on main but fail on the merged branch). This is the correct signal.
- **[Risk] A change that is legitimately correct gets blocked by a sibling's stale assertion.** Mitigation: the retry context explains this scenario and directs the agent at the sibling. If the agent cannot fix the sibling, the operator can disable the directive. The default leans toward fail-closed; individual projects can opt out.
- **[Trade-off] Multi-team scenarios lose the "don't punish me for someone else's test" default.** Accepted — set-core's primary use case is single-team orchestration. Multi-team operators set `integration_smoke_blocking: false` explicitly.
- **[Trade-off] The retry counter is now shared between smoke failures and own-test failures.** If a change fails smoke 2 times and own-test 1 time, it counts as 3 redispatches total and gets abandoned per `e2e_retry_limit`. This is reasonable: the change is consuming 3 full e2e cycles regardless of which phase failed.

## Verification Plan

- **Unit test — smoke fail blocks merge**: monkeypatch `run_command` to return exit_code=1 for the smoke call and exit_code=0 for the own-tests call. Call `_run_integration_gates` with `integration_smoke_blocking=True`. Assert: (a) return value is `False`, (b) `change.status == "integration-e2e-failed"`, (c) own-tests path was NOT called, (d) retry_context mentions the sibling specs.
- **Unit test — smoke pass lets merge proceed**: monkeypatch `run_command` to return exit_code=0 for both calls. Assert return value is `True` and no redispatch.
- **Unit test — directive override restores old behavior**: set `integration_smoke_blocking=False` in directives. Smoke fails, own-tests pass. Assert return value is `True` (merge proceeds with WARNING log), no redispatch triggered.
- **Regression check**: run existing `tests/unit/test_merger_*` files — assert no breakage.
