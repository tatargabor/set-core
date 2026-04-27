# Proposal: Review Gate Integration

## Problem

The review gate (LLM code review via `run_claude_logged`) is registered in the **verifier pipeline** (`handle_change_done` in verifier.py), but the engine bypasses this pipeline entirely. When an agent finishes (loop_status=done), the engine:

1. Sets change status to "done"
2. Adds directly to merge queue
3. Merger runs integration gates (dep_install → build → test → e2e)
4. Merges via ff-only

The verifier pipeline's `handle_change_done` is **never called** from the engine's main code path. Result: review gate, rules gate, scope_check, spec_verify — none of these ever execute. The `review_before_merge: true` config is silently ignored.

## Root Cause

Two separate gate systems evolved independently:
- **Verifier pipeline** (verifier.py:2576): Comprehensive GatePipeline with 10 gates including review
- **Merger integration gates** (merger.py:920): Lightweight inline gates (build/test/e2e only)

The engine (engine.py:1019) detects done → merge queue, never routing through the verifier pipeline.

## Solution

Route "done" changes through the verifier pipeline BEFORE the merge queue. The verifier pipeline already handles retry/fail/pass decisions and adds to merge queue on success.

### Approach: Engine routes done → handle_change_done

Instead of the engine directly setting status="done" and adding to merge queue, it should call `handle_change_done()` which runs the full gate pipeline. The verifier pipeline already adds passing changes to the merge queue (verifier.py:2956).

### What NOT to change
- Merger integration gates stay as-is (they validate post-merge-base integration)
- GatePipeline framework stays as-is
- Review gate implementation stays in verifier.py
- Gate profiles / GateConfig unchanged

## Impact

- Review gate will actually execute when `review_before_merge: true`
- Rules gate, scope_check, spec_verify will execute
- Changes that fail review get retried (agent fixes issues)
- LLM_CALL events for review will appear in dashboard
- Build/test/e2e run twice (verifier pre-merge + merger post-integration) — acceptable, they catch different classes of issues

## Risk

- Low: the verifier pipeline code already exists and is tested
- The engine just needs to call it instead of doing its own done→merge shortcut
