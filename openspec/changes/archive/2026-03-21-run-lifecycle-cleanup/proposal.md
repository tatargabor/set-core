## Why

When a new orchestration run starts on a project that had previous runs, stale artifacts from prior runs cause incorrect UI state, false coverage reports, and confusing diagnostics. Currently:

1. **Coverage data persists across runs** — `coverage.json` retains old change→requirement mappings. The web dashboard shows "merged" for requirements that were merged in a previous run, not the current one.
2. **No run archival** — When a new spec starts, the old state/events are either deleted or overwritten. There's no way to review historical runs.
3. **Digest files survive spec switches inconsistently** — `reset_for_spec_switch()` deletes digest dir, but normal re-runs (same spec, fresh start) don't clean coverage even though the changes are different.
4. **Review findings accumulate** — `review-findings.jsonl` appends across runs, mixing findings from different orchestration cycles.
5. **`cmd_reset --full` and sentinel startup cleanup are independent code paths** with different behaviors — fragile and hard to reason about.

## What

Unified run lifecycle with proper archival and cleanup:

1. **Archive before cleanup** — Before starting a new run, archive the previous run's state, events, coverage, and findings to a timestamped `runs/` directory.
2. **Selective cleanup** — Define clearly what gets cleaned (per-run artifacts) vs preserved (digest from same spec, git history).
3. **Single cleanup function** — Unify sentinel startup cleanup, `reset_for_spec_switch()`, and `cmd_reset` into a shared cleanup path.
4. **Coverage reset on new run** — Always reset `coverage.json` when starting a new orchestration cycle (even with the same spec), since coverage tracks which changes of THIS run cover which requirements.

## Scope

- `bin/set-sentinel` — archive + cleanup on startup, unified `archive_previous_run()` function
- `bin/set-orchestrate` — `cmd_reset` uses shared cleanup
- `lib/set_orch/engine.py` — `_archive_completed_to_jsonl()` writes to run-specific archive dir
- `wt/orchestration/runs/` — timestamped run archive directories

## What to archive (per-run artifacts)

| Artifact | Archive? | Clean? | Why |
|---|---|---|---|
| `orchestration-state.json` | ✅ copy | ✅ delete | Per-run state, stale for new run |
| `orchestration-state-events.jsonl` | ✅ copy | ✅ delete | Per-run event log |
| `coverage.json` | ✅ copy | ✅ reset to empty | Maps changes→requirements for THIS run only |
| `review-findings.jsonl` | ✅ copy | ✅ delete | Per-run review results |
| `review-findings-summary.md` | ✅ copy | ✅ delete | Per-run summary |
| `state-archive.jsonl` | ✅ copy | ✅ delete | Replan archive from THIS run |
| `orchestrator.lock` | ❌ | ✅ delete | Ephemeral lock |
| `.claude/orchestration.log` | ✅ rotate | ✅ truncate | Already has rotation logic |

## What to preserve

| Artifact | Why |
|---|---|
| `digest/requirements.json` | Derived from spec, not from run — regenerated on spec change |
| `digest/dependencies.json` | Same — spec-derived |
| `digest/ambiguities.json` | Same — spec-derived |
| `digest/conventions.json` | Same — spec-derived |
| `digest/index.json` | Same — spec-derived |
| `directives.json` | Config, not run state |
| `config.yaml` | User config |
| `specs/` | Spec files |
| Git branches/worktrees | Handled separately by `clean_old_worktrees()` |
