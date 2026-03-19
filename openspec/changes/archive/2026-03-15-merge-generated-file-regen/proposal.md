## Why

Lock file merge conflicts are the most persistent recurring issue across E2E runs — appearing in runs #3, #8, and #13. The current merge pipeline handles lock file conflicts by accepting "ours" (target branch version), which **silently discards feature branch dependencies**. This can lead to runtime failures when the merged code references packages that exist in the feature's `package.json` but not in the regenerated lock file.

### Evidence from E2E runs

| Run | File | Impact | Resolution |
|-----|------|--------|------------|
| #3 | pnpm-lock.yaml | Merge-blocked, sentinel manual fix | `pnpm install --no-frozen-lockfile` |
| #8 | pnpm-lock.yaml | Merge-blocked | Manual conflict resolution |
| #13 (Bug #24) | pnpm-lock.yaml + `.set-core/.last-memory-commit` | Merge-blocked, 11 leftover conflict markers | `git checkout --ours` + `pnpm install` |

### Root cause analysis

The merge pipeline has 5 conflict resolution layers (auto-resolve → JSON merge → LLM resolve → agent rebase → fingerprint dedup), but generated files need a fundamentally different strategy: **regenerate, don't merge**.

Current flow for lock files:
```
conflict detected → auto_resolve_generated_files() → git checkout --ours → done
                                                      ^^^ WRONG: discards feature deps
```

Correct flow:
```
conflict detected → auto_resolve_generated_files() → git checkout --ours → regenerate lock file → done
                                                                            ^^^ pnpm/yarn/npm install
```

Additionally, `.set-core/` runtime files (`.last-memory-commit`, agent state) sometimes get committed by worktree agents and block merge. These should be cleaned before merge, not resolved during.

### Modular architecture context (post-`planning-quality-profiles`)

The profile system is now live:
- **PM detection**: `profile.detect_package_manager()` and `profile.lockfile_pm_map()` replace hardcoded maps
- **Generated file patterns**: `_get_generated_file_patterns()` merges core + profile patterns; `bin/wt-merge` reads `.generated-file-patterns` file
- **`LOCKFILE_PM_MAP`**: removed from `dispatcher.py` — use `profile.lockfile_pm_map()` or `config.detect_package_manager()`
- **Post-merge install**: `profile.post_merge_install()` is the primary path, legacy fallback exists

Implementation must use profile methods for PM detection and lockfile-to-PM mapping, not hardcoded maps.

### Current code locations

- `bin/wt-merge:45-134` — `GENERATED_FILE_PATTERNS` base list + `.generated-file-patterns` file reading, `auto_resolve_generated_files()`
- `bin/wt-merge:511-554` — pre-merge stashing
- `lib/set_orch/merger.py:314-380` — merge orchestration calling `wt-merge`
- `lib/set_orch/merger.py:561-584` — `_post_merge_deps_install()` (uses `profile.post_merge_install()` with legacy fallback)
- `lib/set_orch/dispatcher.py:46-60` — `_CORE_GENERATED_FILE_PATTERNS` + `_get_generated_file_patterns()`
- `lib/set_orch/dispatcher.py:150-165` — worktree sync generated file handling

## What Changes

### 1. Lock File Regeneration After Conflict Resolution
- After `auto_resolve_generated_files()` accepts "ours" for lock files, detect which lock file was conflicted
- Use `profile.lockfile_pm_map()` to map conflicted lockfile → PM, then run install to regenerate
- Fallback for non-profile projects: hardcoded map in `bin/wt-merge` (pnpm-lock.yaml→pnpm, yarn.lock→yarn, package-lock.json→npm)
- Stage the regenerated lock file and amend the merge commit
- This ensures both sides' dependencies are present

### 2. Unconditional Post-Merge Dependency Install
- `_post_merge_deps_install()` currently checks if `package.json` changed — but lock file conflicts can occur even when only the lock file differs (transitive dependency updates)
- Change: always run dependency install after merge if a lock file was in the conflict set, regardless of package.json changes

### 3. Pre-Merge Runtime File Cleanup
- Before merge, remove `.set-core/` runtime files from the worktree's git index:
  - `.set-core/.last-memory-commit`
  - `.set-core/agents/`
  - `.set-core/orphan-detect/`
- Add these to the worktree's `.gitignore` if not already present
- Prevent worktree agents from committing runtime state files

### 4. Worktree Sync Improvement
- `sync_worktree_with_main()` in dispatcher.py uses same "ours" strategy — apply same regeneration logic
- After sync merge, regenerate lock file in the worktree too

## Capabilities

### New Capabilities
- `lockfile-regeneration-on-conflict`: Auto-regenerate lock files after merge conflict resolution instead of using stale "ours" version
- `pre-merge-runtime-cleanup`: Remove `.set-core/` runtime files from git index before merge

### Modified Capabilities
- `merge-conflict-resolution`: Lock file conflicts trigger regeneration, not just "ours" acceptance
- `post-merge-dependency-install`: Runs unconditionally when lock files were in conflict set
- `worktree-sync`: Applies same regeneration logic after syncing worktree with main

## Impact

- **Modified (set-core)**: `bin/wt-merge` — add lock file regeneration after auto-resolve, use profile lockfile_pm_map with hardcoded fallback
- **Modified (set-core)**: `lib/set_orch/merger.py` — pass conflict file list to post-merge pipeline, unconditional deps install on lock conflict via `profile.post_merge_install()`
- **Modified (set-core)**: `lib/set_orch/dispatcher.py` — lock file regeneration in worktree sync
- **New logic (set-core)**: Pre-merge cleanup of `.set-core/` runtime files in worktree git index
- **No changes to set-project-web/base** — existing `lockfile_pm_map()` and `post_merge_install()` methods are sufficient
- **Risk**: Lock file regeneration adds ~10-30s to merge time (acceptable for preventing recurring failures)
- **No breaking changes**: Existing behavior preserved for non-lock-file conflicts
