## Why

The auto-fix issue pipeline (sentinel detects issue → investigation → diagnosis → policy → fix → resolved) doesn't complete end-to-end. In micro-web-run3, the fix agent successfully implemented all tasks, passed tests, committed, and archived — but the issue state remained "failed" instead of "resolved".

Three root causes:
1. **VALID_TRANSITIONS blocks FIXING → RESOLVED** — only FIXING → {VERIFYING, FAILED, CANCELLED} allowed, but VERIFYING/DEPLOYING are dead-end states with no actual implementation
2. **fixer.collect() loses process reference** — after service restart or sentinel interference, the in-memory `_processes` dict is empty, so collect returns `{success: False}` even when the fix succeeded on disk
3. **Sentinel and pipeline compete** — sentinel independently fixes issues that the pipeline is already handling, causing duplicate work and state confusion

## What Changes

- Simplify state machine: FIXING → RESOLVED directly (skip VERIFYING/DEPLOYING dead-ends)
- Add RESOLVED to VALID_TRANSITIONS from FIXING state
- Make fixer.collect() and investigator.collect() resilient to process loss via filesystem checks
- Mark findings as "pipeline" status when issue pipeline picks them up, so sentinel doesn't double-fix
- Update sentinel skill to check pipeline ownership before Tier 3 fixes

## Capabilities

### Modified Capabilities
- `auto-fix-state-machine` — Simplified FIXING → RESOLVED path with filesystem-based success detection
- `finding-issue-sync` — Bidirectional sync between sentinel findings and issue pipeline

## Impact

- `lib/set_orch/issues/models.py` — VALID_TRANSITIONS update
- `lib/set_orch/issues/manager.py` — simplified FIXING handler (already staged)
- `lib/set_orch/issues/fixer.py` — resilient collect() with filesystem fallback
- `lib/set_orch/issues/investigator.py` — resilient collect() with filesystem fallback
- `lib/set_orch/issues/detector.py` — mark findings as pipeline-owned, persist processed set
- `.claude/commands/set/sentinel.md` — pipeline-ownership check before Tier 3 fixes
