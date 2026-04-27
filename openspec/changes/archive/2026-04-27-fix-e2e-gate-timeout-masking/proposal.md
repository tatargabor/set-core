# Fix E2E Gate Timeout Masking Failures

## Why

The worktree-stage E2E gate (`execute_e2e_gate` in `modules/web/set_project_web/gates.py`) silently returns PASS on runs where Playwright never finished. Three independent defects combine into a single systemic failure mode:

1. **Default timeout is too short.** `Directives.e2e_timeout = 120` and `DEFAULT_E2E_TIMEOUT = 120` (engine.py / verifier.py). Empirical measurement on a realistic web template project (104 tests, Prisma seed + Next.js dev server + Playwright 1.59) shows the full suite runs in ~**156 seconds**. The default is 36s too low and always times out on any non-trivial web project.

2. **Timeout is not distinguished from real failure.** `run_command` returns `exit_code = -1, timed_out = True` on timeout. The gate only checks `exit_code == 0` → treats the timeout as a normal test failure and enters the baseline comparison branch.

3. **The baseline comparison branch misinterprets an incomplete run as "no new failures".** `_extract_e2e_failure_ids(output)` parses Playwright's "numbered failure list" — a block that is only emitted after the run finishes. On a timed-out run, the tail of the output is mid-execution (test progress lines), the regex finds zero matches, and `wt_failures = set()`. The baseline path computes `new_failures = wt_failures - baseline_failures = set() - anything = set()`, hits `if not new_failures: return GateResult("e2e", "pass")`, and **reports PASS with the message "0 pre-existing failures on main (no new regressions)"**.

The combined effect: the worktree-stage e2e gate returns PASS on **every timed-out run**, regardless of whether real test failures would have surfaced. End-to-end run evidence shows one change cycling through 5 worktree-e2e runs, all reporting PASS in ~120-122s (all timed out), while the integration-stage e2e gate (which has a 180s timeout, 1MB output buffer, and no baseline comparison) subsequently failed the change twice and forced redispatch loops totalling 70+ extra minutes.

## What Changes

- **Explicit timeout handling**: when `e2e_cmd_result.timed_out` is True, return `GateResult("e2e", "fail", ...)` with a retry context explaining the incomplete run. Do NOT enter the baseline comparison branch.
- **Unparseable-fail handling**: when `exit_code != 0` and `_extract_e2e_failure_ids` returns an empty set, return `GateResult("e2e", "fail", ...)` with an "infra failure (crash/OOM/format)" retry context. Baseline comparison runs only when there is at least one parseable failure ID.
- **Raise the default `e2e_timeout`** from 120 to 300 seconds in both `lib/set_orch/engine.py:Directives` and `lib/set_orch/verifier.py:DEFAULT_E2E_TIMEOUT`. Measurement-backed margin for realistic web suites.
- **Replace the narrow `max_output_size` caps on both `run_command` calls in `gates.py`** (the worktree run at line 271 had `4000`, the baseline-regen run at line 149 had `8000`) with a shared constant `_E2E_CAPTURE_MAX_BYTES = 4 * 1024 * 1024` (**4 MiB**). Rationale: `_extract_e2e_failure_ids` runs on the captured output — it needs to see *every* failure entry, not a tail slice. The `subprocess_utils` default of 1MB covers ~200 typical failures but can still truncate suites with huge JSON diffs or long stack traces. 4 MiB gives 4x that headroom with trivial memory cost (one short-lived string per gate run) and eliminates "is the buffer big enough?" as a live concern.
- **Lift the gate-runner state storage ceiling for e2e output** from 2000 bytes (head-slice at `gate_runner.py:434` and plain `smart_truncate` at `gate_runner.py:292`) to 32000 bytes using `smart_truncate_structured` with a Playwright-aware keep-pattern, so the numbered failure list is preserved in the state file even after gate completion. Storage is the correct layer to enforce a size bound — it is where output leaves the gate and enters a persistent representation that retries, dashboards, and audits all read. Capture should be uncapped; storage should be bounded.

## Capabilities

### Modified Capabilities
- `web-gates` — tighten the e2e gate contract so timeouts and unparseable failures never mask as PASS; align default timeout with measured web-suite runtime; widen the output buffer to cover the full Playwright failure list.

## Impact

- **`modules/web/set_project_web/gates.py`**: two small guard clauses added to `execute_e2e_gate` (timeout branch + unparseable-fail branch); a new module-level constant `_E2E_CAPTURE_MAX_BYTES = 4 * 1024 * 1024` passed to both `run_command` calls (worktree run at line 271 and baseline-regen run at line 149) so both can capture up to 4 MiB. The downstream `e2e_output[:4000]` slice in the `GateResult(output=...)` construction (line 420) is removed so the full captured output flows to the gate runner. No signature changes.
- **`lib/set_orch/engine.py`**: `Directives.e2e_timeout` default `120` → `300`.
- **`lib/set_orch/verifier.py`**: module constant `DEFAULT_E2E_TIMEOUT` `120` → `300`.
- **`lib/set_orch/gate_runner.py`**: `e2e_output` state storage at `line 292` and `line 434` uses `smart_truncate_structured(result.output, 32000, keep_patterns=...)` with a Playwright numbered-failure pattern, instead of `smart_truncate(..., 2000)` / raw `[:2000]` head slice. Other gates retain their existing 2000 byte budget.
- **`modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml`**: existing `e2e_timeout: 120` line removed (or raised to 300) so consumer-deployed projects inherit the new framework default. This is the primary real-world source of the bug — the core default update alone is not enough because the template override shadowed it.
- **Tests**: new `tests/unit/test_gate_e2e_timeout.py` with four cases — timed-out run returns FAIL, unparseable-fail returns FAIL, real test failure still flows through baseline comparison correctly, and a regression fossil snapshot of the old buggy behavior (pre-fix it was `pass`, post-fix it is `fail`).
- **Backwards compat**: the new defaults only apply to runs that do not explicitly set `e2e_timeout` in orchestration config. Runs that pin `e2e_timeout: 120` in their config keep the old value — but will still benefit from the timeout/unparseable-fail guards, which are unconditional.
- **Risk**: the 300s default makes gate runs feel longer when the suite actually takes 120s+. The trade-off is visibility: a slow but-correct gate is strictly better than a fast-but-lying gate.

## Evidence (empirical measurements on a real web project)

- Full e2e suite run, clean: `104 passed (2.6m)` = **156s**
- `timeout 120 pnpm test:e2e`: exits at 120.005s, reaches 39/104 tests (38% progress), **zero final summary**, **zero failure-list lines** in tail
- `run_command(timeout=120)` direct call: `exit_code=-1`, `timed_out=True`, `stdout=4043 bytes`, `failure-ID regex matches: 0`
- `execute_e2e_gate` unit repro with the above inputs: returns `GateResult(status="pass", output="0 pre-existing failures on main (no new regressions)")` — **confirmed false positive**
