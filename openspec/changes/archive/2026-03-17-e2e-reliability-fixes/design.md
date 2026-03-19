## Architecture

No new modules or abstractions. All changes are minimal edits to existing files.

## Fix 1: Flock fd inheritance (Bug #41)

**File**: `bin/set-sentinel`
**Line**: ~455 (child spawn)

```bash
# Before:
"$SCRIPT_DIR/set-orchestrate" start "$@" &

# After:
"$SCRIPT_DIR/set-orchestrate" start "$@" 9>&- &
```

The `9>&-` closes fd 9 in the child process before exec. The sentinel retains fd 9 (and the flock). When sentinel exits, flock is released regardless of child state.

## Fix 2: Deps reinstall after worktree sync (Bug #29/#33)

**File**: `lib/set_orch/dispatcher.py`
**Function**: `sync_worktree_with_main()`

After the successful merge branch (L216-218), add:

```python
# Check if deps changed in the merge
_reinstall_deps_if_needed(wt_path, merge_base, main_head)
```

New helper `_reinstall_deps_if_needed(wt_path, old_sha, new_sha)`:
1. Run `git diff --name-only {old_sha}..{new_sha}` in the worktree
2. Check if any of `package.json`, `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json` is in the diff
3. If yes: detect PM via `_detect_package_manager(wt_path)`, run `{pm} install`, log result
4. If install fails: warn but don't fail the sync

## Fix 3: Bug index README updates

**Files**: `tests/e2e/minishop/README.md`, `tests/e2e/craftbrew/README.md`

Update status column for:
- Bug #37: "open" → "fixed (`606aec640`)"
- Bug #38/#24: "recurring" → "fixed (`eec894bcb`)"
- Bug #9: "open" → "fixed (`eec894bcb`)"

## Risks

- **fd close**: No risk — `9>&-` is a standard bash fd close. If fd 9 doesn't exist, it's a no-op.
- **deps install**: `pnpm install` in a worktree could conflict with a running agent. Mitigation: the install runs during sync, which happens before the agent resumes (post-merge sync) or before the agent starts (post-bootstrap sync). Non-blocking on failure.
