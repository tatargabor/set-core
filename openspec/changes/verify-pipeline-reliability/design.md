# Design: verify-pipeline-reliability

## Context

The orchestration monitor manages change lifecycle through status transitions: pending → dispatched → running → verifying → merged. Three reliability gaps were identified in E2E testing where changes get permanently stuck or cause cascading failures:

1. **Dead verify agent**: The monitor checks `ralph_pid` (terminal wrapper) to detect dead agents, but the Claude CLI process can die while the terminal wrapper lives. Changes stay in "verifying" forever.
2. **Phantom review**: The review diff computation uses a fallback merge-base (`HEAD~5`) that includes unrelated files from main, causing false review failures.
3. **Removed worktree**: Manual merge intervention removes worktrees, but the monitor keeps trying to poll them, causing repeated failures.

## Goals / Non-Goals

**Goals:**
- Changes in "verifying" with dead agents are auto-recovered within one poll cycle
- Review diffs contain only files modified by the change branch
- Missing worktrees are handled gracefully without sentinel escalation

**Non-Goals:**
- Changing the PID tracking architecture (storing inner Claude PID separately)
- Modifying the wt-loop process management
- Preventing manual worktree removal

## Decisions

### D1: Check child processes of `ralph_pid` for verify liveness

**Choice:** Use `pgrep -P <ralph_pid>` to check if the terminal wrapper has any child processes. If not, treat the agent as dead.

**Alternatives considered:**
- Store inner Claude PID separately → too invasive, requires wt-loop changes
- Use loop-state mtime staleness → already exists but the stale check only runs for `ralph_status == "running"`, not when orch status is "verifying"

**Implementation:** In `_poll_active_changes` (engine.py), add a check specifically for "verifying" changes: if `ralph_pid` is alive but has no children, mark as stalled.

### D2: Add verify timeout guard

**Choice:** Add a `VERIFY_TIMEOUT = 600` (10 min) constant. If a change has been in "verifying" for longer than this, mark as stalled regardless of PID status.

**Rationale:** Verify gates (build + test + review) should complete within 5-10 minutes. A 10-minute timeout catches cases where the process is alive but hung.

**Implementation:** Store `verifying_since` timestamp when transitioning to "verifying". Check elapsed time in `_poll_active_changes`.

### D3: Use `git merge-base HEAD main` for review diff

**Choice:** Replace the `_get_merge_base()` fallback chain with a direct `git merge-base HEAD main` call. Only fall back to `HEAD~10` if merge-base fails (orphan branch, shallow clone).

**Rationale:** `git merge-base` returns the exact fork point, ensuring the diff only contains changes from the branch. The current fallback to `origin/HEAD` → `main` → `master` → `HEAD~5` can resolve to an incorrect base.

**Implementation:** Modify `_get_merge_base()` in verifier.py to use `git merge-base HEAD main` as the primary strategy.

### D4: Pre-poll worktree existence check with auto-transition

**Choice:** Before calling `poll_change()` in `_poll_active_changes`, check `os.path.isdir(worktree_path)`. If missing, auto-set status to "merged" (assuming manual merge removed it).

**Rationale:** A missing worktree for a running/verifying change is a strong signal that manual merge occurred. Auto-transitioning prevents the poll-fail-escalate cycle that crashes the monitor.

**Implementation:** Add existence check at the top of the `_poll_active_changes` loop in engine.py.

## Risks / Trade-offs

- **[Risk] False positive child process check** — some terminal wrappers may not have direct children visible via `pgrep -P`. Mitigation: combine with verify timeout as a safety net.
- **[Risk] Auto-transitioning to "merged" on missing worktree** — if the worktree was removed for a reason other than manual merge (e.g., disk cleanup), the change is incorrectly marked merged. Mitigation: log a clear warning message so the operator notices.
- **[Risk] `git merge-base` failure on shallow clones** — CI environments may use shallow clones. Mitigation: fall back to `HEAD~10` with a logged warning.

## Open Questions

_(none — all decisions are based on observed E2E failure patterns)_
