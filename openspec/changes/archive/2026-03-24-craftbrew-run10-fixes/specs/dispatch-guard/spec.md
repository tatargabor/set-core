# Dispatch Guard

## Requirements

- DISP-001: `dispatch_change()` MUST atomically check that change status is "pending" before creating worktree. If status is not "pending", skip dispatch and return False.
- DISP-002: The status transition "pending" → "dispatched" MUST happen inside `locked_state` before any worktree creation, preventing race conditions between concurrent monitor cycles.
- DISP-003: If a worktree already exists for the change name (e.g., from a previous failed dispatch), the dispatcher MUST handle it gracefully (use existing or clean up stale).
