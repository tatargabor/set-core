## 1. Migration Framework

- [x] 1.1 Add `get_current_branch()` helper function using `git branch --show-current`, returns empty string if not in git repo or detached HEAD
- [x] 1.2 Add `.migrations` JSON file read/write helpers (`migrations_read`, `migrations_write`) in storage directory
- [x] 1.3 Implement migration runner: iterate numbered migration functions, skip already-applied, update `.migrations` after each
- [x] 1.4 Add auto-migrate check at the top of commands that access storage (remember, recall, list, forget, etc.) — skip if `--no-migrate` flag present
- [x] 1.5 Add `cmd_migrate` subcommand: `set-memory migrate` (run pending) and `set-memory migrate --status` (show history)
- [x] 1.6 Add `migrate` to usage text

## 2. Migration 001 — Branch Tags

- [x] 2.1 Implement `migrate_001_branch_tags`: iterate all memories, add `branch:unknown` tag to any memory without a `branch:*` tag
- [x] 2.2 Ensure idempotency: if a memory already has any `branch:*` tag, skip it

## 3. Auto-Tagging in Remember

- [x] 3.1 In `cmd_remember`, after parsing `--tags`, detect current branch via `get_current_branch()`
- [x] 3.2 If branch detected and no `branch:*` tag already present in user tags, append `branch:<name>` to the tags array
- [x] 3.3 If no branch detected (not git repo, detached HEAD), skip silently

## 4. Branch-Boosted Recall

- [x] 4.1 In `cmd_recall`, detect current branch via `get_current_branch()`
- [x] 4.2 If branch detected and no explicit `--tags` provided: issue two queries — (a) tag-filtered `branch:<name>` with `limit // 2 + 1`, (b) unfiltered with full limit
- [x] 4.3 Merge results: branch-tagged first, then unfiltered (deduplicate by ID), cap at requested limit
- [x] 4.4 If no branch or explicit `--tags` provided, use current single-query behavior

## 5. Tests

- [x] 5.1 Test auto-tag: remember on a branch → verify `branch:*` tag present
- [x] 5.2 Test auto-tag skip: remember with existing `branch:custom` tag → no duplicate
- [x] 5.3 Test auto-tag skip: remember outside git repo → no `branch:*` tag
- [x] 5.4 Test recall boost: memories with current branch tag appear first
- [x] 5.5 Test recall no-boost: explicit `--tags` → no branch boost applied
- [x] 5.6 Test migration 001: memories without branch tag get `branch:unknown`
- [x] 5.7 Test migration 001 idempotency: running twice produces same result
- [x] 5.8 Test migration auto-run: first command triggers migration, subsequent commands skip
- [x] 5.9 Test `--no-migrate` flag prevents auto-migration
- [x] 5.10 Test `set-memory migrate --status` output

## 6. Documentation

- [x] 6.1 Update `docs/developer-memory.md` with branch tagging and migration sections
- [x] 6.2 Update `docs/readme-guide.md` if CLI surface changed
- [x] 6.3 Update `README.md` per readme-guide
