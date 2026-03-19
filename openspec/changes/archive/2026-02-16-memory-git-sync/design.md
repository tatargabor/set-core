## Context

The `set-memory` CLI already supports `export` (full JSON dump) and `import` (with UUID-based deduplication). Teams currently share memory by manually copying export files between machines. This change adds a `sync` subcommand family that automates sharing via a git orphan branch.

Key existing infrastructure:
- `bin/set-memory`: bash CLI with `cmd_*` functions, `run_with_lock`, env-var passing to Python
- `resolve_project()`: detects project from git root basename (worktrees share same project)
- Export format: JSON v1 with `{version, format, project, exported_at, count, records}`
- Import dedup: 4-level check via UUID + `metadata.original_id`
- Storage: `~/.local/share/set-core/memory/<project>/`

## Goals / Non-Goals

**Goals:**
- One-command push/pull of memory via git (`set-memory sync push`, `set-memory sync pull`)
- User/machine namespacing so multiple people and devices can contribute
- Skip git operations when nothing changed (zero unnecessary network traffic)
- Work with any git remote (GitHub, GitLab, self-hosted)

**Non-Goals:**
- Auto-sync (hooks, background processes) — sync is always explicit
- LFS support — memory exports are small text JSON, plain git is sufficient
- Conflict resolution — each user/machine writes to its own file, no conflicts possible
- GUI integration for sync — CLI only for v1
- Delta/incremental push — full export is small enough, optimize later if needed

## Decisions

### 1. Orphan branch `set-memory`

Store sync data on an orphan branch named `set-memory` in the same repo. This keeps memory data separate from code, requires no extra infrastructure, and works with any git hosting.

**Alternative considered**: Separate repository for memory. Rejected — adds complexity, requires extra setup per project.

**Alternative considered**: Git notes. Rejected — harder to browse, no directory structure, poor tooling support.

### 2. User/machine directory structure

```
set-memory branch:
├── <user>/
│   └── <machine>/
│       └── memories.json
```

- `user`: lowercase, sanitized from `git config user.name` (spaces → hyphens). Fallback: `whoami`.
- `machine`: lowercase `hostname -s`.

This allows the same person to sync from multiple machines, and multiple people to contribute. Each file is independently owned — no merge conflicts.

**Alternative considered**: Flat structure (`<user>-<machine>.json`). Rejected — harder to browse, doesn't scale visually for teams.

### 3. Local `.sync-state` for skip detection

Store sync state in `~/.local/share/set-core/memory/<project>/.sync-state`:

```json
{
  "last_push_hash": "<sha256 of last pushed export JSON>",
  "last_push_at": "<ISO8601>",
  "last_pull_commit": "<git commit hash of set-memory branch at last pull>",
  "last_pull_at": "<ISO8601>"
}
```

**Push skip logic**: Export memory → sha256 → compare with `last_push_hash`. If identical, print "Nothing to push." and stop (0 git operations).

**Pull skip logic**: `git fetch origin set-memory` → compare remote HEAD with `last_pull_commit`. If identical, print "Up to date." and stop (0 imports).

This ensures minimal network traffic. Push costs nothing if memory hasn't changed. Pull costs one fetch but skips import if remote is unchanged.

### 4. Temp directory for branch operations

Use `mktemp -d` to clone/checkout the orphan branch, perform file operations, commit, push, then clean up. This avoids interfering with the user's working tree or worktree state.

```
push:
  tmpdir=$(mktemp -d)
  git clone --branch set-memory --single-branch --depth 1 origin tmpdir
  (or: git init + fetch if branch doesn't exist yet)
  cp export.json tmpdir/<user>/<machine>/memories.json
  cd tmpdir && git add . && git commit && git push
  rm -rf tmpdir

pull:
  git fetch origin set-memory
  extract files from fetched ref using git show/archive (no full checkout needed)
  set-memory import <each foreign file>
```

**Alternative considered**: Git plumbing (hash-object, mktree, commit-tree). More efficient but significantly harder to implement and debug. Temp dir is simple and reliable.

**Alternative considered**: Git worktree add. Rejected — project already uses set-core worktrees, adding another would be confusing.

### 5. Pull uses `git show` instead of full clone

For pull, we don't need a full checkout. After `git fetch origin set-memory`:
- List files: `git ls-tree -r --name-only origin/set-memory`
- Extract each foreign file: `git show origin/set-memory:<user>/<machine>/memories.json > tmpfile`
- Import each tmpfile

This is faster and lighter than cloning the branch.

### 6. Graceful degradation

- If no git remote exists: error with clear message
- If `set-memory` branch doesn't exist on remote: `push` creates it (orphan), `pull` reports "No sync branch found"
- If shodh-memory not installed: silent no-op (consistent with all other commands)
- If not in a git repo: error with clear message

## Risks / Trade-offs

- [Git history growth] → Each push creates a commit. Mitigated by `--depth 1` clones. Future: `set-memory sync compact` could squash history.
- [Race condition on push] → Two machines push simultaneously. Mitigated: each writes to own directory, git auto-merges. If push fails due to race, user re-runs (the retry will fetch first).
- [Large memory stores] → With thousands of records, full export on every push could be slow. Mitigated: v1 targets typical usage (< 500 records). Future: delta push optimization.
- [No encryption] → Memory content is pushed to git remote in plaintext. Same security model as code. Mitigated: memory content is project-specific technical knowledge, not secrets.
