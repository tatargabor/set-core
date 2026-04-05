# Change: orchestration-logging-hardening

## Why

The orchestration pipeline has ~25 silent failure points where errors, missing data, or skipped steps are swallowed without logging. This caused real bugs to be invisible:

- **craftbrew-run22**: 9/10 agents never got Required Tests section — no log indicated digest_dir was empty
- **micro-web-run25**: test artifacts not collected — NullProfile loaded silently from wrong CWD
- **micro-web-run25**: digest_dir resolved to empty runtime dir — no warning that test-plan.json was missing

Three categories of silent failures:

1. **Silent data loss** — data dropped without trace (test plan not loaded, artifacts not collected, retry context incomplete)
2. **Silent step skip** — pipeline steps skipped without explanation (coverage check, rule injection, spec file injection)
3. **Silent exception swallow** — `except Exception: pass` or bare returns hiding real errors

## What Changes

### 1. WARNING logs for all data-loss paths

Every function that returns empty/None when data was expected gets a WARNING log with the reason and impact. Key targets:
- `_load_test_plan()` — already partially fixed, needs all paths covered
- `_collect_test_artifacts()` — profile load failure, artifact collection failure
- `_build_input_content()` — digest_dir missing, requirements missing
- `load_profile()` — NullProfile fallback logged as WARNING not DEBUG

### 2. INFO logs for pipeline flow visibility

Every major pipeline step gets an INFO log on entry and exit:
- Dispatch: "Dispatching {change}: digest_dir={dir}, requirements={n}, test_plan_entries={n}"
- Gate: "Integration gate pipeline for {change}: {n} gates configured"
- Coverage: "Coverage check: {pct}% ({covered}/{total} reqs)"
- Merge: "Merge pipeline for {change}: gates={pass/fail}, coverage={pass/skip}"

### 3. Structured log context for sentinel anomaly detection

Add a `[ANOMALY]` log prefix for conditions that should never happen in a healthy run:
- Feature change dispatched with 0 requirements
- E2E gate passed with 0 test files
- Coverage check skipped for feature change
- Agent completed with 0 commits
- NullProfile loaded for a project with project-type.yaml

The sentinel can grep for `[ANOMALY]` and surface these in its findings.

### 4. Exception specificity

Replace `except Exception: pass` patterns with specific exception types and context-aware logging. Never swallow exceptions silently — at minimum log WARNING with the exception message.

## Out of Scope

- Changing log levels for existing logs (only adding missing logs)
- Log aggregation infrastructure (ELK, CloudWatch, etc.)
- Log rotation or size limits
- Structured JSON logging format (current text format is fine)
