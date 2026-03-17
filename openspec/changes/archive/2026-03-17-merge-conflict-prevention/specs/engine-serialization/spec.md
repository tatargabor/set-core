# Engine Merge-Before-Dispatch Serialization

## Requirements

### ES-1: Merge queue check before dispatch
The engine loop MUST check `state.merge_queue` before calling `_dispatch_ready_safe()`. If the queue is non-empty, merge all pending changes before dispatching new ones.

### ES-2: Post-drain dispatch
After draining the merge queue, the engine MUST call `_dispatch_ready_safe()` to dispatch any newly-unblocked changes. This ensures the pipeline doesn't stall after merges complete.

### ES-3: Token budget path
The token-budget-exceeded code path (engine.py ~L382) also calls `_retry_merge_queue_safe()`. This MUST use the same drain-then-dispatch pattern.

### ES-4: Checkpoint path
The checkpoint path (engine.py ~L347) calls `_retry_merge_queue_safe()`. This SHOULD also drain fully before continuing, to prevent merge queue items from accumulating across checkpoint boundaries.

### ES-5: Self-watchdog path
The self-watchdog recovery path (~L1054) calls `_retry_merge_queue_safe()`. This SHOULD use the same helper for consistency.

## Acceptance Criteria

- When a change enters `done` status and is queued for merge, it merges BEFORE any new change is dispatched
- Archive commits are on main BEFORE new worktrees are created
- No archive race: new worktrees always see the latest openspec/changes/ deletions
