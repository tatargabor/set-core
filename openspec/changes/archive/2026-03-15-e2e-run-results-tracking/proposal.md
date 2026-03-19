## Why

E2E tests (minishop, craftbrew) run against set-core but there's no automated tracking of what changed between runs and whether previous bugs regressed. Currently the sentinel starts monitoring without knowing what to watch for, findings are written manually, and the user must launch run.sh + sentinel separately. Two projects can run in parallel with independent results.

## What Changes

- Add a **"Last Run Results"** section to `E2E-GUIDE.md` that auto-updates per project (minishop/craftbrew) with run metrics, set-core commit delta, open regressions, and comparison to previous run
- Add a **"Sentinel Startup"** section to `E2E-GUIDE.md` defining the full lifecycle: prep phase (subagent collects context), launch phase (sentinel runs run.sh + starts orchestration), monitor phase (existing), wrap-up phase (results collection + guide update + commit)
- Extend `wt-e2e-report` to update the "Last Run Results" section in E2E-GUIDE.md after each run — parse state.json, git log for commit delta, findings.md for open regressions
- The sentinel becomes the **full lifecycle owner** — it launches the E2E run, monitors it, and records results. The user only tells it which project to run.

## Capabilities

### New Capabilities
- `e2e-run-results`: Automated per-project run results tracking in E2E-GUIDE.md — commit delta, metrics, regression check, previous run comparison
- `sentinel-e2e-lifecycle`: Sentinel owns full E2E lifecycle — prep (subagent context collection), launch (run.sh + set-sentinel), monitor (existing), wrap-up (results + commit)

### Modified Capabilities
<!-- No existing spec-level behavior changes — this adds new sections to the guide and extends reporting -->

## Impact

- `tests/e2e/E2E-GUIDE.md` — two new sections added (Last Run Results, Sentinel Startup)
- `bin/wt-e2e-report` — extended to parse and update guide sections
- Sentinel skill/prompt — extended with prep/launch/wrap-up phases
- Per-project findings files — open bug detection for regression tracking
- No breaking changes — existing monitoring workflow still works, new lifecycle is additive
