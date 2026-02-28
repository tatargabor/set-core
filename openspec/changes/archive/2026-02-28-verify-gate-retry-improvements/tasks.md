## 1. Retry Context Passthrough

- [x] 1.1 In `resume_change()`, read `retry_context` from state via jq (JSON-escaped string, needs double-unescape), use as task description when non-empty, fall back to generic "Continue $change_name: $scope" when empty
- [x] 1.2 In `resume_change()`, clear `retry_context` from state after reading it (set to `null` via `update_change_field`)

## 2. Review Failure Retry Context

- [x] 2.1 In `handle_change_done()` review-critical retry path (~line 2843), build `retry_context` with review feedback (similar to test failure path): include review output (first 500 chars), change name, scope
- [x] 2.2 Store the review `retry_context` in state via `update_change_field` before calling `resume_change()`

## 3. Memory-Enriched Retries

- [x] 3.1 In `handle_change_done()` test-failure retry path (~line 2807), after building `retry_context`, call `orch_recall` with change scope as query (no tag filter, limit 3), append non-empty result as `## Context from Memory` section (max 1000 chars) to retry_context
- [x] 3.2 In `handle_change_done()` review-critical retry path, same pattern: recall with scope, append to retry_context
- [x] 3.3 In merge conflict rebase path (new, task 4.1), recall with "$change_name merge conflict recent merges" as query, append to retry_context

## 4. Agent-Assisted Merge Rebase

- [x] 4.1 In `merge_change()` conflict path (~line 2988), after setting status to `"merge-blocked"`, check if `merge_retry_count` is 0: if so, build a `retry_context` asking the agent to merge main into the branch, set status to `"merge-rebase"`, call `resume_change()`
- [x] 4.2 In `handle_change_done()`, detect `"merge-rebase"` status at function entry: if status was `"merge-rebase"`, skip the verify gate pipeline (tests/review/verify) and jump directly to the merge step
- [x] 4.3 In `handle_change_done()` merge-rebase path, if `merge_change()` still fails after agent rebase, increment `merge_retry_count` and fall through to `retry_merge_queue` flow (set status `"merge-blocked"`)
- [x] 4.4 In `retry_merge_queue()`, skip changes with status `"merge-rebase"` (agent is working on them, don't retry merge in parallel)
