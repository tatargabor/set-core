## Why

E2E orchestration runs consistently show 40% of changes hitting avoidable verify gate failures that resolve on retry. Three recurring patterns waste ~43 minutes and ~70K+ tokens per run: (1) build errors caught late because tests run before build, (2) translation JSON merge conflicts that the LLM resolver fails on, and (3) watchdog log spam from non-actionable "PID alive" warnings. These are configuration/ordering issues, not fundamental bugs.

## What Changes

- **Swap verify gate order to build-first**: Change the verify gate pipeline from test→build→e2e to build→test→e2e. Build catches type errors (e.g. `string` vs `"hu" | "en"`) in ~10s vs waiting for test+build+retry cycle (~90s). This saves one full retry cycle for the most common failure mode.
- **Add programmatic JSON merge for translation files**: Extend wt-merge's auto-resolve strategy (currently only handles package.json) to also handle `.json` translation files using the same jq deep-merge approach. Translation files (en.json, hu.json) are the #1 merge conflict source because multiple changes add keys to the same file.
- **Reduce watchdog log noise**: Change the "hash loop but PID alive — skipping escalation" message from WARN to DEBUG level. This is informational (the system correctly decides not to act), not a warning condition. Reduces log noise by ~150 events per run.

## Capabilities

### New Capabilities
- `json-translation-merge`: Programmatic deep-merge for JSON translation files in wt-merge, avoiding LLM-based conflict resolution for additive-only changes

### Modified Capabilities
- `verify-gate`: Change step execution order from test→build→e2e to build→test→e2e
- `orchestration-watchdog`: Change "PID alive" hash loop message from WARN to DEBUG

## Impact

- `lib/orchestration/verifier.sh` — reorder gate steps (build before test)
- `bin/wt-merge` — add `auto_resolve_json_files()` function, hook into merge flow
- `lib/orchestration/watchdog.sh` — change log level for PID-alive case
- `openspec/specs/verify-gate/spec.md` — update step order in spec
- `openspec/specs/orchestration-watchdog/spec.md` — update log level expectation
