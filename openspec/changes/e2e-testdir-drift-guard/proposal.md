# Change: e2e-testdir-drift-guard

## Why

When the e2e gate invokes Playwright against a spec file path (e.g. `pnpm test:e2e tests/e2e/blog-list-with-filter.spec.ts`) but the project's `playwright.config.ts` declares a `testDir` that does not contain that file (e.g. `testDir: "e2e"`), Playwright crashes with:

```
Error: No tests found.
Make sure that arguments are regular expressions matching test files.
```

It then exits with code 1. The set-core e2e gate captures `exit_code=1` with no parseable `failedTests[]` block and falls into the unparseable-fail path with the misleading message `[no parseable failure list — likely crash, OOM, or formatter issue]`. This burns a `verify_retry_count` slot diagnosing what is actually a config-versus-specs path mismatch, not a crash.

Empirical evidence from a recent local run (`micro-web-run-20260501-1805` after merging the `blog-list-with-filter` worktree into main):

- Worktree's `playwright.config.ts`: `testDir: "tests/e2e"` and `globalSetup: "./tests/e2e/global-setup.ts"`.
- Main branch's `playwright.config.ts` (carried over from an earlier `test-infrastructure-setup` change scaffolded against an older convention): `testDir: "e2e"` and `globalSetup: "./e2e/global-setup.ts"`.
- Merged spec file lives at `tests/e2e/blog-list-with-filter.spec.ts` (11 `test()` blocks).
- Main retains stale `e2e/smoke.spec.ts` and `e2e/global-setup.ts` from the initial scaffold.
- The merge promoted the worktree's spec files but NOT its `playwright.config.ts` change. Result: the integration gate ran specs at `tests/e2e/...` against a config that only reads `e2e/`, producing the unparseable failure described above.

The agent had to read the failure log, deduce the config-spec drift manually, and patch both the config and the file layout — exactly the kind of recoverable bootstrap mismatch that `e2e-dep-drift-guard` (archived 2026-04-21) and `e2e-env-drift-guard` (active) already handle for their respective failure classes. This change extends the same two-layer pattern (failure-class detection + in-gate self-heal, plus forensic markers and no retry-budget consumption) to testdir drift.

The set-core scaffold template (`modules/web/set_project_web/templates/nextjs/playwright.config.ts`) already declares the canonical `testDir: "./tests/e2e"` — but consumer projects that were scaffolded under an older convention, or whose configs have since been hand-edited, do not benefit from that. The gate-runner self-heal is the safety net those projects need.

## What Changes

Three layers of defense, mirroring the dep-drift / env-drift pair:

**Layer 2a — Failure-parser classification (`modules/web/set_project_web/gates.py`):**

- Recognize `Error: No tests found.` Playwright signature on the unparseable-fail path.
- Surface a distinct error message in the gate's retry-context output (so when self-heal cannot recover, the agent and operator see "playwright testDir vs spec file path mismatch" instead of "likely crash, OOM, or formatter issue").
- This alone — independent of any self-heal — ends the misleading-diagnostic burn that costs operator time.

**Layer 2b — Gate-runner self-heal (`modules/web/set_project_web/gates.py`):**

- Add `_extract_testdir_drift(e2e_output, project_root)` returning `True` when Playwright output contains `Error: No tests found` AND at least one `*.spec.ts` file exists somewhere under the project root.
- Add `_resolve_canonical_testdir(project_root)` that returns the directory containing the most spec files, with a tiebreaker preferring `tests/e2e/` (set-core's canonical path that all dispatched agents target) over `e2e/` (legacy scaffold path).
- Add `_resync_playwright_config_testdir(project_root, new_testdir)` that rewrites `testDir:` and `globalSetup:` lines in `playwright.config.ts` atomically, preserving all other lines. Also moves any stale `e2e/global-setup.ts` content into the new path if and only if no `tests/e2e/global-setup.ts` exists yet (otherwise leaves the canonical one in place).
- Add `_self_heal_testdir_drift(...)` mirroring `_self_heal_db_env_drift`'s contract: returns `(healed, recovered_testdir, rerun_result)` or `None` if the signature did not match. Runs at most one in-gate rerun.
- Wire the new self-heal into `execute_e2e_gate` AFTER `_self_heal_db_env_drift` on the unparseable-fail path. All three self-heals are gated by the same `self_heal_attempted` flag — at most one self-heal per gate invocation.
- New INFO logs: `e2e_testdir_drift_detected`, `e2e_testdir_self_heal_resynced_and_rerun`. New `GateResult.output` marker: `[self-heal: synced playwright.config.ts testDir from <old> to <new>]`.

**Layer 2c — Template canary (`modules/web/set_project_web/verifier.py` or scaffold post-init check):**

- Add a verify-time check that compares `playwright.config.ts` `testDir` to where spec files actually live in the worktree.
- Emit a `warn`-level GateResult (not `fail`) if they disagree — this catches the drift at PR-time, before merge, complementing the runtime self-heal.
- Universal: works for any spec layout; not tied to a specific path convention.
- This is the inexpensive prevention layer parallel to the dispatcher-prompt strengthening that landed for the `page.goto` lint.

**No core (Layer 1) changes.** The drift only affects web/Playwright projects. The existing `verify_retry_count` invariant carries forward — self-heal does not increment.

**No template overwrite required.** The scaffold `playwright.config.ts` already declares `testDir: "./tests/e2e"`. New projects start in the canonical state; existing projects benefit from the verify canary and the gate self-heal.

**No consumer redeploy required.** The running sentinel loads `gates.py` and `verifier.py` from the same venv; restarting the supervisor process picks up both new self-heal and new canary on the next gate invocation. The Python module cache means a venv-level restart (not a `set-project init`) is the deployment step.

## Capabilities

### New Capabilities

- `e2e-testdir-drift-guard`: Failure-parser classification of Playwright "No tests found" as a distinct testdir-mismatch failure class, gate-runner self-heal that rewrites `playwright.config.ts` `testDir` to align with the project's actual spec layout, and a verify-gate canary that warns at PR-time when config and specs diverge.

### Modified Capabilities

<!-- none — e2e-dep-drift-guard handles npm-package drift, e2e-env-drift-guard handles DATABASE_URL/schema drift, this is the parallel testdir-drift concern. The three are siblings and live in distinct capability specs. -->

## Impact

- **Code**: `modules/web/set_project_web/gates.py` (new `_extract_testdir_drift`, `_resolve_canonical_testdir`, `_resync_playwright_config_testdir`, `_self_heal_testdir_drift`, integration into `execute_e2e_gate`); `modules/web/set_project_web/verifier.py` (new `_lint_playwright_testdir_consistency` running in the verify gate).
- **Tests**: unit tests for each new helper (drift signature regex, canonical-testdir resolver across mixed layouts, atomic rewrite of `playwright.config.ts` preserving comments and other fields), plus an integration test that fabricates a worktree with stale config and merged-elsewhere specs and asserts the gate returns `pass` with the self-heal marker without incrementing `verify_retry_count`.
- **Retry budget**: self-heal does NOT consume `verify_retry_count`, keeping the 4-attempt budget for real failures (mirrors `e2e-dep-drift-guard` / `e2e-env-drift-guard`).
- **Logs**: new INFO events `e2e_testdir_drift_detected`, `e2e_testdir_self_heal_resynced_and_rerun`. Forensics + `set-run-logs` will surface these alongside the existing self-heal events.
- **Behavior invariance**: when `playwright.config.ts` `testDir` matches where specs actually live, zero overhead — the cheap signature check fires only on the unparseable-fail path.
- **Dependencies**: no new packages. Stdlib only (`os.walk`, `re`, atomic-write via `tempfile`/`os.replace`).
- **Forensic visibility**: a single regex (`\[self-heal: `) finds any self-healed gate run in `set-run-logs`; the `synced playwright.config.ts testDir from ... to ...` marker is distinct from the dep-drift `installed <pkg>` and env-drift `synced .env from config.yaml` markers, so manual log inspection can identify the failure class.
- **Empirical grounding**: the recent `micro-web-run-20260501-1805` run produces the exact failure mode this change targets — a worktree-resident manual fix landed in that run, and this change forward-ports the pattern into set-core proper.
