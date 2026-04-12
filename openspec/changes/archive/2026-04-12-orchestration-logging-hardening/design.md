# Design: orchestration-logging-hardening

## Core Principle

**Every empty return must explain itself.** If a function returns `[]`, `""`, `None`, or `False` when success would return data, it must log WHY at WARNING level. The sentinel and human operator must be able to reconstruct what happened from the log alone.

## Log Levels

| Level | When | Example |
|-------|------|---------|
| DEBUG | Expected empty paths (no rules dir, no conventions) | "No .claude/rules/ dir — skipping rule injection" |
| INFO | Pipeline flow milestones | "Dispatching cart-and-promotions: 8 reqs, 39 test entries" |
| WARNING | Unexpected missing data or skipped steps | "digest_dir empty — agent won't get Required Tests" |
| ERROR | Data loss or unrecoverable failure | "Test artifact collection failed — screenshots lost" |
| `[ANOMALY]` | Should-never-happen conditions | "[ANOMALY] Feature change dispatched with 0 requirements" |

## Design Decisions

### 1. `[ANOMALY]` prefix for sentinel-parseable warnings

**Decision:** Prefix certain WARNING/ERROR messages with `[ANOMALY]` so the sentinel can grep the orchestration log and surface issues.

**Why:** The sentinel already polls the orchestration state. Adding log scanning gives it early-warning for conditions that don't yet show up in state (e.g., "digest_dir empty" precedes "agent writes too few tests" by 30+ minutes).

**Implementation:** Simple string prefix, no framework change. The sentinel skill can add `grep -c '\[ANOMALY\]' orchestration.log` to its health check.

### 2. Dispatch summary log

**Decision:** Single INFO log line at dispatch time summarizing all critical context:

```
INFO: Dispatching cart-and-promotions: requirements=8, test_plan_entries=39,
  digest_dir=/path/to/digest, design_context=yes, retry=0
```

**Why:** Currently you need to read 5 different log lines to understand what the agent received. One summary line makes it grep-able and debuggable.

### 3. Gate pipeline summary log

**Decision:** After all gates complete for a change, log a summary:

```
INFO: Gate pipeline for cart-and-promotions: build=pass(1.2s) test=pass(3.4s)
  e2e_smoke=pass(12s,6t) e2e_own=pass(25s,7t) coverage=pass(82%) — PASSED
```

**Why:** Currently gate results are logged individually but there's no single line showing the full picture.

### 4. NullProfile as WARNING not DEBUG

**Decision:** When `load_profile()` returns NullProfile and a `project-type.yaml` exists (but is invalid/empty), log WARNING. When no `project-type.yaml` exists at all, log DEBUG.

**Why:** NullProfile with existing config file = something is wrong. NullProfile without config = expected for non-set-core projects.

## Files to Modify

| File | Changes | Log Count |
|------|---------|-----------|
| `dispatcher.py` | dispatch summary, data-loss warnings | ~8 |
| `merger.py` | gate summary, artifact warnings, coverage skip | ~6 |
| `engine.py` | anomaly detection, exception logging, flow logs | ~5 |
| `planner.py` | test plan injection log, validation log | ~3 |
| `profile_loader.py` | NullProfile warning | ~2 |
| `verifier.py` | verification skip warnings | ~2 |
| `state.py` | deserialization warnings | ~1 |
