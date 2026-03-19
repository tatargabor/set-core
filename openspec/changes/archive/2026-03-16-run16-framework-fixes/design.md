## Context

The orchestration pipeline (sentinel → monitor → dispatch → verify → merge) has 4 framework bugs found in E2E Run #16 that caused 5 manual interventions. All are in the core orchestration modules (`verifier.py`, `dispatcher.py`, `engine.py`, `set-sentinel`).

Current state:
- **Verify retries**: single `verify_retry_count` counter shared by build-fix, test-fix, review-fix, and scope-fix — a build self-heal consumes the same budget as a real verify failure
- **Generated file matching**: `_CORE_GENERATED_FILE_PATTERNS` uses basename-only matching (`os.path.basename(f)` checked against a set of filenames). `.claude/*` runtime files are not in the set, and subdirectory paths can't match basename patterns
- **Sentinel flock**: `flock -n 9` with no PID validation — if the previous sentinel dies but the lock fd persists (zombie, /proc stale entry), restart is blocked until manual `rm sentinel.lock`
- **Monitor resume**: no special handling for changes in "verifying" status with all gates already passed — monitor re-dispatches instead of proceeding to merge

## Goals / Non-Goals

**Goals:**
- Build-fix iterations don't consume verify retry budget
- All `.claude/*` runtime files auto-resolved during merge conflicts
- Sentinel restarts cleanly when previous instance is dead
- Monitor resume recognizes completed verify gates and proceeds to merge

**Non-Goals:**
- Changing the overall retry limit architecture (keep `max_verify_retries` directive)
- Adding new config directives
- Modifying the merge queue or merge retry logic itself
- Fixing the sentinel/monitor crash root cause (Bug #5 — separate investigation)

## Decisions

### D1: Build-fix uses separate counter, not a new field

Instead of adding a `build_retry_count` field to state, **don't increment `verify_retry_count` for build failures**. The build-fix retry at `verifier.py:1306` sets status to `verify-failed` and dispatches a resume — but the agent typically fixes the build and the next verify attempt runs the full gate. The fix: when build fails, dispatch resume with retry context but **don't increment `verify_retry_count`**. The next verify run will increment if the *actual* gate (test/review/scope) fails.

Rationale: simpler than a new field. The retry budget protects against infinite loops — build-fix cycles are bounded by the Ralph loop's own iteration limit (typically 3). No state schema change needed.

### D2: Prefix-based matching for `.claude/` in generated file patterns

Extend the conflict matching in `dispatcher.py:155-160` to check both:
1. `os.path.basename(f) in generated_patterns` (existing — for lockfiles)
2. `f.startswith(".claude/")` (new — for all `.claude/*` runtime files)

Any file under `.claude/` is framework-generated and safe to auto-resolve with `--theirs`. This covers current files and any future `.claude/` additions without maintaining an explicit list.

### D3: PID validation before flock rejection in set-sentinel

In `bin/set-sentinel`, before the flock fails:
1. Read PID from `sentinel.pid`
2. `kill -0 $pid` to check liveness
3. If dead → `rm sentinel.lock`, retry flock
4. If alive → exit with current error message

This is a 5-line bash addition before the existing flock block.

### D4: Resume-time verify gate check in engine

In `_poll_active_changes` (engine.py), when a change has status "verifying":
- Read verify gate results from state (`test_result`, `build_result`, `review_result`, `scope_result`)
- If all blocking gates are "pass" (or "skipped") and the change has been in "verifying" for >30s (debounce), proceed to merge
- This handles the case where monitor died between verify pass and merge initiation

## Risks / Trade-offs

- **D1 risk**: An agent that repeatedly fails build without fixing it could loop longer before hitting the retry limit. Mitigated by Ralph's iteration limit (3) — the agent will exhaust its own budget before the verify retry budget matters.
- **D2 risk**: Auto-resolving all `.claude/*` with `--theirs` could lose sentinel-side state edits. Acceptable because `.claude/*` in worktrees is agent-local state, not shared.
- **D3 risk**: Race between PID check and process death. Minimal — if the process dies between check and flock, the flock will succeed on retry.
- **D4 risk**: False positive merge on stale gate results from a previous verify run. Mitigated by the 30s debounce and by checking that all blocking gates have results (not just some).
