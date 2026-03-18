# Proposal: verify-pipeline-reliability

## Why

The verify pipeline has three reliability gaps that cause changes to get permanently stuck, force manual sentinel intervention, and waste retries on false positive reviews. In E2E testing, these bugs required manual merge for the majority of changes — only 1 in 15 merged autonomously.

## What Changes

- **Fix: detect dead verify agents** — the monitor's poll loop doesn't detect dead Claude CLI processes when the terminal wrapper PID is still alive, leaving changes stuck in "verifying" status forever
- **Fix: review diff scope** — the verify code review uses a merge-base fallback (`HEAD~5`) that includes unrelated scaffold files, causing false review failures and wasted retries
- **Fix: skip poll for removed worktrees** — after manual merge + worktree removal, the monitor keeps trying to poll/sync the missing worktree, causing repeated failures that escalate to sentinel shutdown

## Capabilities

### New Capabilities

- `verify-dead-agent-detection` — detect and recover changes with dead verify agents
- `review-diff-scoping` — scope review diffs to only branch-modified files
- `removed-worktree-resilience` — gracefully handle missing worktrees in the poll loop

### Modified Capabilities

_(none — no existing specs affected)_

## Impact

- **Files**: `lib/wt_orch/verifier.py`, `lib/wt_orch/engine.py`, `lib/wt_orch/dispatcher.py`
- **Risk**: Low — all changes are additive guards/checks, no existing behavior modified
- **Testing**: E2E run validation against the same project that exposed these bugs
