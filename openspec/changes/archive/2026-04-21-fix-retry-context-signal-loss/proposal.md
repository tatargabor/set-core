# Change: fix-retry-context-signal-loss

## Why

Recent multi-change E2E runs have exhibited a failure pattern where a single change loops to `max_verify_retries` without converging, while the implementation agent silently engages in **scope creep** — modifying shared files belonging to other changes. Post-mortem on one such run revealed three compounding framework bugs, all rooted in the same cause: **the impl agent never receives actionable evidence about why a gate failed**. The agent then substitutes random shared-code edits for the missing signal, breaking tests it was never asked to touch.

### Bug A — E2E gate retry_context drops the error tail (ACTIVE)

The web module's E2E gate constructs the retry_context as:

```python
f"E2E output:\n{e2e_output[:2000]}\n"
```

A head-only slice. Before that slice, gates.py prepends a ~1500-char failing-test header (`"E2E: 33 NEW failures\nNew failures: tests/e2e/...:150, :159, ..."`). The combined budget leaves ~500 chars for actual stdout — which in a Next.js/Prisma project is pure infrastructure noise (`"Prisma schema loaded..."`, `"Running generate..."`). Playwright assertion errors — stack traces, `expected 5, got 3`, element-not-found — appear near the END of stdout and get chopped.

Observed consequence: the impl agent sees a list of failing tests but cannot tell whether "my new code broke an existing test" or "an existing test is stale". It interprets the gate's literal instruction *"Fix the failing E2E tests or the code they test"* as license to rewrite shared modules (auth, cart, checkout) — indistinguishable from the required fix surface.

### Bug B — spec_verify gate conflates max_turns with real FAIL

`verifier.py` escalates spec_verify from sonnet to opus on `exit_code != 0`. If opus also returns `exit_code != 0`, the gate is marked FAIL and the retry_context handed to the impl agent is the LLM's own transcript.

`exit_code != 0` fires on three different conditions:
1. LLM explicitly output `VERIFY_RESULT: FAIL` with CRITICAL findings — correct gate FAIL.
2. LLM hit `--max-turns 40` before producing a verdict — infrastructure failure.
3. LLM timed out or crashed — infrastructure failure.

Cases 2 and 3 currently consume a retry slot and trigger implementation re-dispatch. The retry_context is the partial stream-json transcript — tool-call metadata, no actionable diagnosis. The impl agent cannot respond to this and tends to thrash on the same symptoms, exhausting budget.

### Bug C — Unit test gate is never invoked in the default web template

`modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` ships with:

```yaml
# test_command: pnpm test
# e2e_command: npx playwright test
```

Both commented out. Consumer projects initialize with `test_command = ""`, so the unit test gate is permanently `skipped`. Meanwhile the scaffold installs `vitest` and a `"test": "vitest run"` script. Fast unit-level feedback (validator logic, pure function behavior) is thus never exercised before the heavy e2e gate runs — regressions that unit tests would catch in seconds escalate into e2e failures that take minutes and consume retry slots.

### Broader audit

Grep across `lib/set_orch/` and `modules/` for head-only `[:\d+]` slices on stdout/stderr/output identified three additional call sites that can drop evidence:
- `verifier.py:2008` — phase-end E2E output for replan context (`[:8000]`)
- `verifier.py:2764` — review_output in review_history persistence (`[:1500]`)
- `cli.py:693`, `orch_memory.py:150` — lower impact

The `smart_truncate_structured` utility in `lib/set_orch/truncate.py` already provides head+tail+error-line-preservation exactly for this purpose. The fix is to route all user-visible (LLM-bound) retry_context through it and reserve plain `[:N]` slices for cosmetic logging only.

## What Changes

- **Bug A fix** — Replace `e2e_output[:2000]` in the web module's E2E gate retry_context with `smart_truncate_structured` at a larger budget (6000 chars), preserving head and tail plus any lines matching error/FAIL/Expected/TypeError patterns. Add unit test covering a synthetic Playwright output where assertion errors appear only at the tail.
- **Bug B fix** — Parse stream-json output from `run_claude_logged` to detect `terminal_reason: max_turns` and timeout. When detected, do NOT mark the spec_verify gate as FAIL and do NOT consume a retry slot; instead retry once with double max-turns budget (80), and if that also terminates on max_turns, emit a new `GATE_INFRA_FAIL` event and abstain (treat as gate skipped with surfaced anomaly, not code fault).
- **Bug C fix** — Uncomment `test_command: pnpm test` in the web template's `config.yaml` so newly initialized consumer projects get unit-test gating on by default. The gate already no-ops when no test files exist, so there is no regression risk.
- **Truncation audit** — Migrate the other three head-only slice call sites identified in the audit to `smart_truncate_structured`. Add a unit test that fails if a new `[:\d+]` slice is introduced on an output going into retry_context or replan context (lint-style test over source files).
- **Observability** — Add `infra_fail: bool` field to the `VERIFY_GATE` event `data` payload when a gate fails for infrastructure reasons rather than real findings, so run logs can be filtered.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `verification-gates`: E2E retry_context format (tail-preservation); spec_verify infra vs FAIL classification; unit test gate default-on; truncation strategy for all LLM-bound gate outputs.

## Impact

- **Core**: `lib/set_orch/verifier.py` (spec_verify max_turns detection, truncation audit at lines 2008 and 2764), `lib/set_orch/events.py` (if new event type) or just extend the `VERIFY_GATE` `data` payload.
- **Module**: `modules/web/set_project_web/gates.py` (E2E retry_context truncation), `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` (uncomment test_command).
- **Tests**: unit tests for Playwright tail-preservation, stream-json max_turns detection, and a source-level audit test.
- **No consumer-visible behavior change** except that impl agents now receive actionable failure evidence and spec_verify stops thrashing on infrastructure failures. Fresh consumer projects will run unit tests by default; existing ones are unaffected unless reinitialized.

## Out of Scope

- Planner changes, scope-check enforcement of proposal-declared file sets, and the "scope creep" problem at the prompt level. Bug A is expected to remove the primary trigger for scope creep; enforcement is a separate future change.
- Review gate behavior (working correctly).
- Alternative verify-gate architectures (e.g., replacing LLM-based verify with deterministic checks). Out of scope for this change.
- Changes to any `[:N]` slice that is NOT bound for an LLM prompt / retry_context / replan context (plain logging slices remain as-is).
