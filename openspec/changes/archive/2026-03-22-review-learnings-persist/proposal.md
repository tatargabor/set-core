# Proposal: review-learnings-persist

## Problem

Review gate findings repeat across runs. An agent makes the same security mistakes (no auth on API routes, `as any` casts, missing rate limiting) that were already caught and fixed in a previous run. The cross-change learnings injection (`_build_review_learnings` in dispatcher.py) only works **within a single run** — the first change in each run has zero learnings, and when a run is interrupted, all accumulated knowledge is lost.

Additionally, learnings are not project-type-aware. A web project's typical review failures (XSS, CSRF, NextAuth type safety) are irrelevant to a CLI tool project, but the current system doesn't distinguish.

## Proposed Solution

Persist review learnings into the **project type profile** so they survive across runs and are scoped to the correct project type.

Three components:

1. **Extract & persist** — After each change merge (not just run end), extract CRITICAL/HIGH patterns from `review-findings.jsonl` and write them to a profile-owned learnings file (e.g., `modules/web/.review-learnings.jsonl`).

2. **Profile method: `review_learnings_checklist()`** — New method on `ProjectType` ABC that reads the persisted learnings and returns a compact "DO NOT" checklist (max ~15 lines). The web module overrides this to combine persisted dynamic learnings with a static baseline checklist.

3. **Inject at dispatch** — The dispatcher calls `profile.review_learnings_checklist()` and appends it to input.md alongside the existing cross-change learnings. This means even the first change of a new run gets the checklist.

## Scope

- `lib/set_orch/profile_types.py` — add `review_learnings_checklist()` and `persist_review_learnings()` methods
- `lib/set_orch/dispatcher.py` — inject profile checklist into input.md
- `lib/set_orch/engine.py` — call `persist_review_learnings()` after each merge (not just run end)
- `lib/set_orch/review_clusters.py` — extend clusters with new patterns seen in E2E runs
- `modules/web/set_project_web/project_type.py` — implement web-specific baseline + dynamic learnings
- `modules/web/set_project_web/review_baseline.md` — static web security checklist
- `tests/unit/test_review_learnings.py` — unit tests

## Non-Goals

- Changing the review gate prompt itself
- Changing review severity classification
- Adding new gates
