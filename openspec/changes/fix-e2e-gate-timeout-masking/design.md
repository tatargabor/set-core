# Design: Fix E2E Gate Timeout Masking

## Context

The worktree-stage E2E gate (`modules/web/set_project_web/gates.py:execute_e2e_gate`) is the primary signal that a change's tests pass before merge. In end-to-end run telemetry, this gate has been reporting PASS on changes whose tests actually fail — the failures only surface later when the merger's integration-stage e2e gate re-runs the same command and reports FAIL. The result: expensive redispatch loops that would have been caught earlier if the worktree-stage gate told the truth.

Tracing through the code:

1. `execute_e2e_gate` calls `run_command(["bash", "-c", e2e_command], timeout=e2e_timeout, max_output_size=4000)` (gates.py:268). The default `e2e_timeout` comes from `Directives.e2e_timeout = 120` (engine.py:80).
2. `run_command` wraps `subprocess.run(..., timeout=e2e_timeout)`. On timeout, `subprocess_utils.py:107` catches `TimeoutExpired` and returns `CommandResult(exit_code=-1, timed_out=True, stdout=<partial>, stderr=<partial>)`.
3. `execute_e2e_gate` only inspects `exit_code`: `raw_status = "pass" if exit_code == 0 else "fail"` (gates.py:299). `timed_out` is ignored.
4. With `raw_status == "fail"`, the code enters the baseline-comparison branch at gates.py:321.
5. `wt_failures = _extract_e2e_failure_ids(e2e_output)` (gates.py:322). The regex `^\s*\d+\)\s+\[.*?\]\s+[›»]\s+([^\s:]+\.spec\.\w+:\d+)` matches Playwright's "numbered failure list" — which is only printed after the run finishes. On an incomplete (timed-out) run, the tail of stdout is test-progress lines, not a failure list. The regex finds zero matches. `wt_failures = set()`.
6. Baseline is computed on `project_root` (main branch checkout) — a clean run that usually produces `baseline.failures = []`.
7. `new_failures = wt_failures - baseline_failures = set() - set() = set()`.
8. `if not new_failures: return GateResult("e2e", "pass", ...)` (gates.py:348-354). **Gate reports PASS.**

The output header in this failure mode is the misleading `"E2E: 0 pre-existing failures on main (no new regressions)"` — which is literally true (nothing on main failed) but masks that the worktree run never completed.

### Empirical measurements

On a realistic web template project (Next.js 15 + Prisma 6 + Playwright 1.59, 104 e2e tests, Prisma seed + dev server):

- Clean full-suite run: `104 passed (2.6m)` = **156 seconds wall-clock**
- `timeout 120 pnpm test:e2e` (SIGTERM at 120s): exits at 120.005s, reaches **39/104 tests** (38% progress), no final summary in output
- Python `run_command(timeout=120, max_output_size=4000)` direct call: `exit_code=-1`, `timed_out=True`, `stdout=4043 bytes`, `stderr=4043 bytes`, **zero failure-ID regex matches** on combined output
- Unit repro of `execute_e2e_gate` with the above inputs: returns `GateResult(status="pass")` — **confirmed false positive**

## Goals / Non-Goals

**Goals:**
- Timeouts surface as FAIL, never masked as PASS via baseline comparison.
- Unparseable-output failures (where exit_code ≠ 0 but no failure-list can be extracted) surface as FAIL, never masked.
- Default `e2e_timeout` is at least 2x the measured full-suite runtime for a realistic web project.
- The output buffer kept by `run_command` is large enough to always include the final Playwright summary + failure list.

**Non-Goals:**
- Restructuring the baseline comparison concept itself. The baseline comparison is useful when the wt run produces a parseable failure list and the main run also does; the fix restricts its applicability, not its logic.
- Changing the integration-stage (merger) e2e gate. That gate already has a 180s timeout, 1MB output buffer, and no baseline masking. The bug lives only in the worktree-stage gate.
- Introducing adaptive timeouts (measure + scale). A flat higher default is simpler and the overhead is bounded by the actual suite runtime.
- Changing how `_extract_e2e_failure_ids` parses failures. The regex is correct for completed runs; the problem is not the parser but the blind trust in its empty result.

## Decisions

### 1. Two guard clauses at the top of the baseline-comparison branch

**Choice:** Insert two `if` clauses in `execute_e2e_gate` immediately after `raw_status` is computed and before the baseline comparison runs:

```python
if e2e_cmd_result.timed_out:
    return GateResult(
        "e2e", "fail",
        output=f"E2E timed out after {e2e_timeout}s — Playwright did not finish "
               f"(incomplete run, cannot assess failures)\n\n" + e2e_output[:3000],
        retry_context=(
            f"E2E gate timed out after {e2e_timeout}s. The test suite did not "
            f"finish executing — this is an infrastructure signal, not an "
            f"assertion failure. Check: webServer startup, prisma db push, "
            f"test count, slow fixtures, network calls."
        ),
    )

# Real failure path — extract failure IDs
wt_failures = _extract_e2e_failure_ids(e2e_output)
if not wt_failures:
    return GateResult(
        "e2e", "fail",
        output=f"E2E exited with code {e2e_cmd_result.exit_code} but no parseable "
               f"failure list — likely crash, OOM, or formatter issue\n\n"
               + e2e_output[:3000],
        retry_context=(
            f"E2E gate failed with exit_code={e2e_cmd_result.exit_code} but "
            f"Playwright did not emit a failure list. This usually means the "
            f"suite crashed before completing — check the worktree for stack "
            f"traces, OOM kills, or webServer startup errors."
        ),
    )
```

**Why two separate clauses?** Timeouts and crashes are both "incomplete run" scenarios but have different root causes. The distinct retry contexts tell the agent whether to look at wall-clock (timeout → reduce test count or mark slow tests `@slow`) versus look at error traces (crash → fix the crashing code). Lumping them together loses the signal.

**Alternatives considered:**
- Pass `timed_out` into the baseline comparison and treat it as "everything failed" — rejected: we do not know what failed, assuming everything failed corrupts subsequent retry context.
- Retry the gate automatically on timeout — rejected: the retry would also timeout, and retries should be the agent's choice, not the gate's.
- Kill the baseline comparison entirely and always treat failures as failures — rejected: baseline comparison does catch real pre-existing failures on projects that have them, and removing it changes behavior for passing runs as well. Out of scope.

### 2. Raise `DEFAULT_E2E_TIMEOUT` and `Directives.e2e_timeout` from 120 to 300

**Choice:** Change the two default constants in `engine.py:80` and `verifier.py:82`.

**Why 300 and not 180 or 240?** Empirical measurement shows 156s for a 104-test suite on a commodity dev machine. Adding margin for (1) slower CI/test machines, (2) initial Prisma generate + db push + seed overhead on a cold node_modules, (3) webServer cold start, (4) tests that grow over time as the project adds features — 300s gives roughly 2x headroom, which is the standard engineering margin for "won't flake on variance". 180 (50% margin) is too tight; 600+ would make real hangs take too long to detect.

**Alternatives considered:**
- Auto-scale timeout based on test count — rejected: extra complexity, and test count is available only after parsing, not before.
- Separate directive for worktree vs integration stage — rejected: both stages need realistic time budgets, and having two knobs is worse than one good default.
- Leave the default alone and require each consumer to set 300+ explicitly — rejected: the default should be correct out of the box for realistic web projects.

### 3. Raise `max_output_size` passed to `run_command` from 4000 to 32000 inside `execute_e2e_gate`

**Choice:** Change the single call site at gates.py:271.

**Why 32000 and not 8000 or 65536?** Playwright's final failure list + summary on a 10-failure run is roughly 5-10KB. A full Playwright HTML reporter output with stack traces is typically 20-30KB. 32KB covers the realistic worst case while staying a small fraction of the default 1MB ceiling. 8KB is too tight for projects with many failures; 64KB is wasteful and makes state files bloat.

**Scope:** Only `execute_e2e_gate` (the single call at gates.py:271). Other `run_command` callers keep their current sizes.

**Alternatives considered:**
- Use the default 1MB `max_output_size` — rejected: 1MB stdout + 1MB stderr means the gate result can hold 2MB of output, which bloats state files and retry prompts beyond what is useful.
- Keep 4000 and rely on tail truncation — rejected: tail truncation cuts mid-line and loses the summary header that tells the agent what went wrong.

### 4. Do not touch the baseline comparison logic

**Choice:** The baseline comparison stays as-is — it runs only when there is at least one parseable failure ID in `wt_failures`. The two guard clauses handle the cases where baseline comparison is meaningless (timeout, unparseable fail).

**Why?** Baseline comparison is correct for projects with genuinely flaky or pre-existing-broken tests on main. Its fundamental logic is sound; the bug is in WHEN it runs, not in WHAT it does. Fixing WHEN is a 10-line change; rewriting WHAT is a different OpenSpec change.

## Risks / Trade-offs

- **[Risk] Existing projects that pin `e2e_timeout: 120` in config still time out.** Mitigation: the timeout guard clause catches this — they now get FAIL instead of a false PASS. Operators will see the real problem and can raise the timeout.
- **[Risk] The 300s default makes passing runs appear slower in the dashboard.** Mitigation: the gate returns as soon as exit_code=0 arrives, so passing runs are still whatever the suite's real runtime is (~156s in the measured case). Only actually-slow runs feel the full 300s.
- **[Risk] The unparseable-fail guard fires on legitimate `_extract_e2e_failure_ids` parser misses (new Playwright version changes the format).** Mitigation: the retry context explains "exit code N but no parseable failure list" so an operator can tell whether the issue is genuine crash vs parser drift. If parser drift becomes a real issue, the regex can be updated separately.
- **[Risk] Wider output buffer (32KB) inflates state file size.** Mitigation: 32KB × N changes × M retries is still sub-megabyte for realistic runs. Bounded and acceptable.
- **[Trade-off] The fix does not address the deeper question of "should the worktree-stage gate exist at all if integration stage re-runs the same tests?"** That is a legitimate future design question (separate change) but out of scope here. The current change makes the worktree-stage gate honest, which is a prerequisite for answering the deeper question later.

## Verification Plan

- **Unit test**: synthetic `CommandResult(exit_code=-1, timed_out=True, stdout=<mid-run progress>, stderr="")` plus monkeypatched `run_git` for baseline branch detection → assert `execute_e2e_gate` returns `status="fail"`.
- **Unit test**: synthetic `CommandResult(exit_code=2, timed_out=False, stdout=<crash trace with no numbered failure list>, stderr="")` → assert `status="fail"`.
- **Unit test**: synthetic `CommandResult(exit_code=1, timed_out=False, stdout=<real Playwright failure list>, stderr="")` with matching baseline → assert baseline comparison still runs and `status="fail"` with the failure ID in the retry context.
- **Regression repro**: the pre-fix bug can be reproduced with the exact inputs measured in the investigation — the test should ASSERT the new behavior (FAIL), and would have failed on the pre-fix code.
- **Constants check**: grep for hardcoded `120` near `e2e_timeout` references; all should now reference the `300` default or the constant.
