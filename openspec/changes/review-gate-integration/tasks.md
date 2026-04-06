# Tasks: Review Gate Integration

## 1. Engine: let poll_change handle done detection

The engine's dead-agent handler (engine.py L1022-1033) catches `loop_status=done` and marks the change as `done` directly, bypassing `poll_change()` → `handle_change_done()` which runs the gate pipeline.

- [x] 1.1 In `_poll_active_changes()` (engine.py ~L1022), when agent is dead but loop_status=done: instead of marking done + continue, let it fall through to `poll_change()`. The agent being dead is fine — `poll_change` reads loop-state (not the live process). Remove the `continue` and the direct status="done" assignment. Keep the CHANGE_DONE event emission and issue resolution.
- [x] 1.2 Verify `poll_change` handles dead-agent + done loop_status correctly: it reads loop-state.json, accumulates tokens, detects ralph_status="done", calls `handle_change_done()`. The agent doesn't need to be alive for this.

## 2. Engine: prevent double merge queue addition

After `handle_change_done` runs gates and adds to merge queue, the engine's orphan "done" handler must not re-add.

- [x] 2.1 In the engine's orphan done handler (the code that logs "orphaned 'done' change"), check if the change is already in `merge_queue` before adding. The `handle_change_done` already adds passing changes to merge_queue (verifier.py:2956).
- [x] 2.2 Also check: after `handle_change_done` sets status to verify-failed or dispatches retry, the engine should not treat these as orphaned done changes.

## 3. Verifier: ensure gate pipeline handles already-dead agent

- [x] 3.1 Verify `handle_change_done` doesn't require a live agent process. It reads the worktree diff, runs gates, and may dispatch agent for retry. The agent being dead is expected — it completed its work.
- [x] 3.2 If review gate fails (CRITICAL findings), `handle_change_done` calls `resume_change()` which starts a NEW agent process to fix the findings. This is correct behavior.

## 4. Test and validate

- [ ] 4.1 E2E validation: run micro-web and verify review gate appears in Gate pipeline log and LLM call log dashboard
