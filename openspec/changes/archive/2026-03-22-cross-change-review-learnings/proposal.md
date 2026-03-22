# Proposal: cross-change-review-learnings

## Why

Review findings from one change don't reach sibling changes mid-run. If change A gets a CRITICAL for "no auth middleware", change B (dispatched later) has no idea and may repeat the same mistake. The `review-findings.jsonl` is centralized but only read at run end by `_persist_run_learnings()`. Agents waste tokens rediscovering the same patterns.

## What Changes

- **ENHANCE**: `dispatcher.py` — at dispatch time, read centralized `review-findings.jsonl`, extract recurring/clustered patterns from sibling changes, inject a compact "Lessons from Prior Changes" section into `input.md`
- **ENHANCE**: `DispatchContext` — add `review_learnings: str` field
- **ENHANCE**: `_build_input_content()` — render the new field as a section in input.md

## Capabilities

### Modified Capabilities
- `dispatcher`: Cross-change review learnings injection at dispatch time

## Impact

- **Modified files**: `lib/set_orch/dispatcher.py` (new helper + DispatchContext field + input.md section)
- **Risk**: Low — additive only, no behavioral change to existing gates or review logic
- **Dependencies**: None — reads existing `review-findings.jsonl` format
