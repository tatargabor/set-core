## Context

`wt-close` removes a git worktree and optionally deletes the associated branch. Currently it has a `--force` flag that bypasses all safety checks — uncommitted change detection and interactive branch deletion prompts. The GUI and wt-loop agent always use `--force`, making silent code loss possible when branches have unpushed commits.

The worktree and the main repo share the same `.git` directory, so commits on a worktree branch are locally accessible from the main repo. However, if the branch is deleted without pushing to remote or merging to master, those commits are lost (only recoverable via `git reflog` within a limited time window).

## Goals / Non-Goals

**Goals:**
- Prevent accidental code loss when closing worktrees
- Remove `--force` flag so agents/scripts cannot bypass safety checks
- Provide non-interactive flags (`--keep-branch`, `--delete-branch`) that are safe by design
- Warn users explicitly when branch deletion would lose unmerged/unpushed commits

**Non-Goals:**
- Automatic merging or pushing during close (that's `wt-merge` / `wt-push`'s job)
- Changing `wt-merge` behavior
- Adding stash functionality to wt-close

## Decisions

### Decision 1: Remove `--force` entirely

**Choice**: Remove `--force` flag. No way to skip safety checks.

**Rationale**: The `--force` flag exists to allow non-interactive use, but it conflates "skip prompts" with "skip safety checks". Agents will always choose `--force` because they can't answer interactive prompts, which means safety checks are always skipped in automated contexts — exactly where they're most needed.

**Alternative considered**: Keep `--force` but add safety checks that can't be skipped. Rejected because `--force` semantically means "do it anyway" and would confuse users/agents.

### Decision 2: Two non-interactive flags replace `--force`

**Choice**: Add `--keep-branch` and `--delete-branch` as non-interactive alternatives.

- `--keep-branch`: Close worktree, keep branch. Always safe. This is what GUI/agents should use.
- `--delete-branch`: Close worktree, delete branch. Fails with error if branch has commits not in master AND not on remote. This ensures no silent code loss.

**Rationale**: Separating the intent ("keep" vs "delete") from the safety mechanism makes it impossible to accidentally lose code. The safe path (`--keep-branch`) is the easiest path.

### Decision 3: Unmerged commit detection via git

**Choice**: Use `git log master..branch` to detect commits not in master, and check `git branch -r` for remote branch existence plus `git log origin/branch..branch` for unpushed commits.

Logic for branch deletion safety:
```
branch_commits_not_in_master = git log --oneline master..<branch>
remote_exists = git branch -r has origin/<branch>
unpushed = remote_exists && git log origin/<branch>..<branch>

safe_to_delete = (no branch_commits_not_in_master) OR (remote_exists AND no unpushed)
```

If safe: delete silently.
If unsafe (interactive): show warning with commit count, require explicit "yes" confirmation.
If unsafe (non-interactive `--delete-branch`): fail with error, suggest pushing first.

### Decision 4: GUI uses `--keep-branch`

**Choice**: GUI changes from `--force` to `--keep-branch`. Branch cleanup happens separately (via `wt-merge` or manual deletion).

**Rationale**: The GUI close button should be a simple, safe operation. Users who want to also delete the branch can do so through other means.

## Risks / Trade-offs

- **[Breaking change]** Existing scripts using `--force` will break. → Mitigation: Clear error message suggesting `--keep-branch` or `--delete-branch` as alternatives.
- **[Agent behavior change]** wt-loop or other agents calling `wt-close --force` will fail. → Mitigation: Update any agent scripts/skills that call wt-close.
- **[Extra step for cleanup]** Users who want to delete a branch with unmerged commits need to explicitly confirm interactively. → This is intentional friction to prevent code loss.
