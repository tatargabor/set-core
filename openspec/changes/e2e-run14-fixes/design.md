## Context

The merge pipeline runs post-merge steps on the main branch after each successful `wt-merge`. Two of these steps have bugs discovered during E2E testing:

1. **Dependency install** (`_post_merge_deps_install`) uses `git diff HEAD~1` to detect `package.json` changes, but multi-commit merges (impl + archive commits) push `package.json` beyond HEAD~1.
2. **Spec coverage gate** treats `spec_coverage_result=fail` identically to build/test failures, triggering a full agent redispatch that burns ~80k tokens for minimal gain.

## Goals / Non-Goals

**Goals:**
- Post-merge deps install correctly detects package.json changes regardless of commit count
- Spec coverage failures allow merge with a warning instead of triggering retry
- Both fixes are minimal, surgical changes (< 20 lines each)

**Non-Goals:**
- Redesigning the verify gate pipeline
- Adding new gate types or metrics
- Changing how build/test/review retries work (those are correct)
- Fixing design context frame matching (separate change)

## Decisions

### D1: Save pre-merge SHA before wt-merge call

**Decision**: Capture `git rev-parse HEAD` before the merge, pass it to `_post_merge_deps_install()` for accurate diffing.

**Alternatives considered**:
- *Merge-base computation*: `git merge-base HEAD main` — more complex, can be confused by history rewrites, requires knowing the main branch name
- *Pre-merge tag*: `git tag orch/{name}-pre-merge` — adds tag pollution, requires cleanup
- *Always install if node_modules missing*: Simple but runs `pnpm install` even when package.json didn't change (wasteful for non-JS changes)

**Rationale**: Pre-merge SHA is the most direct solution. The SHA is already available (we're about to merge), costs one `git rev-parse` call, and works regardless of merge strategy (FF, 3-way, squash).

### D2: Spec coverage as non-blocking warning

**Decision**: When `VERIFY_RESULT: FAIL` is found in verify output, log a warning and set `spec_coverage_result=fail` but do NOT set `verify_ok = False`. The change proceeds to merge.

**Alternatives considered**:
- *Single retry with focused prompt*: Still uses tokens, adds conditional retry logic complexity
- *Separate retry limit for spec coverage*: Different max_retries per gate type — harder to maintain and reason about
- *Disable spec coverage entirely*: Loses visibility into spec compliance

**Rationale**: Spec coverage is advisory — it measures documentation quality, not functional correctness. The review gate already catches security and quality issues. Making it non-blocking saves ~80k tokens per occurrence while preserving observability via the state field and VERIFY_GATE event.

## Risks / Trade-offs

- [Risk: spec documentation drift] Agents may never fix spec coverage since it's non-blocking → Mitigation: spec_coverage_result is still recorded in state and events. Users can audit post-run.
- [Risk: pre_merge_sha not set in edge cases] If merge_change is called from a different code path → Mitigation: fallback to `HEAD~1` when pre_merge_sha is empty (backwards-compatible).
