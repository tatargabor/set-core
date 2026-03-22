## 1. Extract cluster constants

- [x] 1.1 Move `_CLUSTERS` dict from `engine.py:_persist_run_learnings()` to a module-level constant `REVIEW_PATTERN_CLUSTERS` in `review_clusters.py`, update `_persist_run_learnings()` to use it [REQ: cross-change-learnings-injected-at-dispatch]

## 2. Build review learnings helper

- [x] 2.1 Add `review_learnings: str = ""` field to `DispatchContext` dataclass in `dispatcher.py` [REQ: cross-change-learnings-injected-at-dispatch]
- [x] 2.2 Create `_build_review_learnings(findings_path: str, exclude_change: str) -> str` in `dispatcher.py`: read JSONL, filter out `exclude_change`, keep only CRITICAL+HIGH, cluster by keywords, deduplicate, format as compact markdown (max 15 lines) [REQ: findings-are-clustered-and-compact, only-critical-and-high-findings-injected]
- [x] 2.3 In `dispatch_change()`, after building `DispatchContext`, call `_build_review_learnings()` with the centralized JSONL path and set `ctx.review_learnings` [REQ: cross-change-learnings-injected-at-dispatch]

## 3. Render in input.md

- [x] 3.1 In `_build_input_content()`, add a `## Lessons from Prior Changes` section when `ctx.review_learnings` is non-empty, including a reference to the full JSONL path [REQ: cross-change-learnings-injected-at-dispatch]

## 4. Tests

- [x] 4.1 Unit test: JSONL with findings from 3 changes, dispatching change D → only findings from A, B, C appear [REQ: cross-change-learnings-injected-at-dispatch, scenario: only-own-findings-exist]
- [x] 4.2 Unit test: empty JSONL → no section generated [REQ: cross-change-learnings-injected-at-dispatch, scenario: no-prior-findings-exist]
- [x] 4.3 Unit test: multiple changes with same "no auth" pattern → clustered into one line with change count [REQ: findings-are-clustered-and-compact, scenario: multiple-changes-hit-same-pattern]
- [x] 4.4 Unit test: MEDIUM findings filtered out, only CRITICAL+HIGH remain [REQ: only-critical-and-high-findings-injected]
- [x] 4.5 Run existing tests: must all pass (1 pre-existing failure unrelated to this change)
