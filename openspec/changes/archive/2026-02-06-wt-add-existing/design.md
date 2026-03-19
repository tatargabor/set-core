## Context

The `wt-add` command and the GUI "Add" button currently only accept git worktrees (directories where `.git` is a file pointing to the main repo). This was the original design since set-core was built around `git worktree`.

However, the system has evolved — `wt-status` already displays the main repo alongside worktrees, and branches are first-class citizens in the GUI table. Users want to register standalone git repositories (clones, forks, or the main checkout of a different project) via the Add button, but the strict `is_worktree()` check rejects them.

The change-id derivation and project registration logic already works for both cases — the only blocker is the validation gate.

## Goals / Non-Goals

**Goals:**
- Allow `wt-add` to accept any valid git repository, not just worktrees
- Maintain validation that the selected directory is actually a git repo
- Keep backward compatibility — worktrees continue to work exactly as before
- Update GUI labels/tooltips to reflect the broader scope

**Non-Goals:**
- Changing how `wt-status` discovers or lists entries (it already handles both)
- Adding a separate "Add Repository" flow — one unified Add path
- Supporting bare repositories (no working tree)

## Decisions

### D1: Relax `is_worktree()` to `is_git_repo()` validation

**Decision**: Replace the strict worktree check with a git repository check. Accept any directory that is a valid git working tree.

**Rationale**: The registration logic (`register_worktree()`, `derive_change_id()`) already handles both cases. The worktree-only check is an unnecessary gate. A simple `git rev-parse --is-inside-work-tree` check is sufficient.

**Alternative considered**: Adding a separate `--allow-repo` flag. Rejected — it adds complexity for no benefit. If it's a valid git repo, we should accept it.

### D2: Adapt `get_main_repo` logic for non-worktree repos

**Decision**: When the directory is a regular git repo (`.git` is a directory), treat it as its own "main repo" — `main_repo = wt_path`. When it's a worktree (`.git` is a file), use the existing `get_main_repo_from_worktree()` logic.

**Rationale**: The main repo path is used for project auto-detection and openspec init. For a standalone clone, the repo itself is the relevant path.

### D3: Adjust change-id derivation for non-worktree repos

**Decision**: For non-worktree repos, the `derive_change_id()` function should:
1. Use `--as <change-id>` if provided (existing behavior)
2. Try branch name patterns (`change/X`, `feature/X`) — already works
3. Fall back to directory name — already works

The only adjustment needed is in `get_main_repo_from_worktree()` which is called by `derive_change_id()` for the `repo-<changeid>` pattern. For non-worktree repos, this function returns empty, so that pattern is skipped — which is correct behavior.

**Rationale**: No new logic needed. The existing fallback chain handles it.

### D4: Update GUI labels

**Decision**: Change UI text from "worktree"-specific to generic:
- Button tooltip: "Add existing worktree" → "Add existing repository or worktree"
- Dialog title: "Select Existing Worktree" → "Select Git Repository"
- Command output dialog title: "Adding worktree" → "Adding repository"

**Rationale**: Users should understand they can select any git repo, not just worktrees.

### D5: Mark non-worktree entries distinctly in projects.json

**Decision**: Add `"is_worktree": false` to the registration metadata for non-worktree repos (alongside existing `added_manually: true`). Worktrees get `"is_worktree": true`.

**Rationale**: Downstream tools may need to distinguish between worktrees and standalone repos (e.g., `wt-close` uses `git worktree remove` which only works on actual worktrees).

## Risks / Trade-offs

**[Risk] Close/remove behavior differs for repos vs worktrees** → The `wt-close` command uses `git worktree remove`. For non-worktree repos, this would fail. Mitigation: `wt-close` should check the `is_worktree` flag and only deregister (remove from projects.json) without attempting `git worktree remove`.

**[Risk] Duplicate registration if same repo added as both main and worktree** → If user adds a repo that is already shown as a project's main repo, it could appear twice. Mitigation: Check if the path already appears in `wt-status` output before registering. For now, the "already registered" check in `register_worktree()` handles the exact-path case.

**[Trade-off] Simpler validation means more potential for user confusion** → A user might accidentally add a non-project directory. Acceptable because: the error cost is low (just deregister), and showing the git repo info during add confirms what's being registered.
