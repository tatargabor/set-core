## Context

The merge pipeline resolves lock file conflicts by accepting the target branch version (`git checkout --ours`), which silently discards dependencies added by the feature branch. This causes runtime failures when merged code references packages that exist in its `package.json` but are missing from the lock file. Additionally, runtime state files (`.wt-tools/` directory) sometimes get committed by worktree agents and create unnecessary merge conflicts.

**Current flow:**
1. `auto_resolve_generated_files()` in `bin/wt-merge` accepts "ours" for lock files
2. `_post_merge_deps_install()` in `merger.py` only runs install if `package.json` changed in the merge diff
3. `sync_worktree_with_main()` in `dispatcher.py` uses the same "ours" strategy with no regeneration
4. No pre-merge cleanup of runtime files

**Profile system context:** The profile system (`profile.lockfile_pm_map()`, `profile.post_merge_install()`, `config.detect_package_manager()`) is live and provides PM detection and lockfile mapping. Implementation must use these profile methods, with legacy fallback for non-profile projects.

## Goals / Non-Goals

**Goals:**
- Regenerate lock files after conflict resolution so both branches' dependencies are preserved
- Run dependency install unconditionally when lock files were in the conflict set (not gated on `package.json` changes)
- Clean runtime files from git index before merge to prevent spurious conflicts
- Apply the same regeneration logic to worktree sync (`sync_worktree_with_main`)

**Non-Goals:**
- Changing how non-lock-file generated files are resolved (`.tsbuildinfo`, `dist/`, etc. still use "ours")
- Modifying the profile interface itself (existing `lockfile_pm_map()`, `post_merge_install()`, `detect_package_manager()` are sufficient)
- Handling lock file conflicts that involve structural corruption (those should still fail to merge-blocked)
- Optimizing install speed (the 10-30s overhead is acceptable)

## Decisions

### D1: Regenerate via install command, not lock file merge

**Decision:** After accepting "ours" for a lock file, run the project's install command (`pnpm install`, `yarn install`, `npm install`) to regenerate the lock file from the merged `package.json`.

**Alternatives considered:**
- **Merge lock files programmatically** (like `auto_resolve_package_json` does for `package.json`): Lock files are machine-generated with complex internal structures (content hashes, integrity checksums). Programmatic merge is fragile and PM-specific. Running the PM's own install command is the canonical way to regenerate.
- **Always accept "theirs" instead of "ours"**: This would discard the target branch's transitive dependency updates. Neither side alone is correct; regeneration from merged `package.json` is needed.

**Rationale:** The PM's install command is the authoritative lock file generator. It reads the merged `package.json` and produces a correct, consistent lock file that includes all dependencies from both branches.

### D2: Lock file detection via profile.lockfile_pm_map() with hardcoded fallback

**Decision:** Use `profile.lockfile_pm_map()` to map conflicted lock file names to their package manager. Fall back to a hardcoded map in `bin/wt-merge` for non-profile projects (pnpm-lock.yaml -> pnpm, yarn.lock -> yarn, package-lock.json -> npm).

**Alternatives considered:**
- **Profile only, no fallback**: Would break projects that haven't adopted the profile system yet.
- **Hardcoded only**: Would bypass the extension point, violating the modular architecture.

**Rationale:** Profile-first with legacy fallback follows the established pattern used by `_post_merge_deps_install()`, `config.detect_package_manager()`, and other profile-aware functions.

### D3: Pass conflict metadata from wt-merge to merger.py via exit output

**Decision:** `bin/wt-merge` already prints info messages about auto-resolved files. Enhance this output to include a machine-readable marker (e.g., `LOCKFILE_CONFLICTED=<filename>`) that `merger.py` can parse from stdout to determine whether a lock file was in the conflict set.

**Alternatives considered:**
- **Temp file signaling**: Write a file like `.wt-tools/.merge-lockfile-conflict`. Adds filesystem state that needs cleanup.
- **Always run install unconditionally after every merge**: Wasteful when no lock file was involved. Adds 10-30s to every merge.
- **Separate wt-merge exit codes**: Exit codes are already used for success/failure. Adding more codes is fragile.

**Rationale:** Stdout parsing is already used by `merger.py` to process `wt-merge` output. Adding a structured marker is low-risk and self-documenting.

### D4: Regeneration happens in wt-merge (bash), not merger.py (Python)

**Decision:** Lock file regeneration after conflict resolution happens inside `bin/wt-merge`'s `auto_resolve_generated_files()` function, immediately after accepting "ours" for lock files. The regenerated file is staged and included in the merge commit.

**Alternatives considered:**
- **Regeneration in merger.py's post-merge pipeline**: This would regenerate after the merge commit, requiring an additional commit or amend. It also wouldn't cover the `wt-merge` standalone usage path.
- **Separate regeneration script**: Over-engineering for a focused fix.

**Rationale:** Regenerating in `wt-merge` ensures the merge commit itself contains the correct lock file, whether called from `merger.py` or standalone. It keeps the "resolve + regenerate" logic atomic.

### D5: Pre-merge cleanup removes runtime files from index, adds to .gitignore

**Decision:** Before merge, run `git rm --cached` on `.wt-tools/` runtime files (`.last-memory-commit`, `agents/`, `orphan-detect/`) and ensure they're in `.gitignore`. This is done as a pre-merge step in `bin/wt-merge`.

**Alternatives considered:**
- **Post-merge cleanup**: Too late; the files already caused conflicts.
- **Prevent commits in worktree agents**: Would require changes to many agent workflows. Fragile enforcement.
- **Only .gitignore, no index removal**: Doesn't help if files are already tracked.

**Rationale:** Cleaning the index before merge prevents the conflict entirely. Adding to `.gitignore` prevents re-tracking. Belt-and-suspenders approach.

### D6: Unconditional install when lock file was conflicted

**Decision:** `_post_merge_deps_install()` in `merger.py` is enhanced to accept a parameter indicating whether a lock file was in the conflict set. When true, install runs unconditionally (not gated on `package.json` changes).

**Alternatives considered:**
- **Always run install unconditionally**: Wasteful overhead on merges with no dependency changes.
- **Only rely on wt-merge regeneration (D4)**: The merger.py post-merge install serves as defense-in-depth and handles edge cases where wt-merge regeneration might not fully resolve (e.g., install in project root vs. worktree path differences).

**Rationale:** Defense-in-depth. The wt-merge regeneration (D4) is the primary fix, but the merger.py unconditional install catches edge cases and ensures `node_modules` is consistent.

## Risks / Trade-offs

- **[Risk] Lock file regeneration fails (network error, corrupted package.json)** -> Mitigation: Log warning, continue with the "ours" version. The merge is still better than being blocked. Existing error handling in `_post_merge_deps_install()` already follows this pattern.

- **[Risk] Install command takes too long (>60s)** -> Mitigation: Use the existing 300s timeout from `_post_merge_deps_install()`. Lock file installs with an existing `node_modules` are typically fast (10-30s) since only delta packages are fetched.

- **[Risk] Regenerated lock file differs from what either branch had** -> This is the correct behavior. The regenerated lock file reflects the merged `package.json`, which is the union of both branches' dependencies. This is analogous to rebuilding after a code merge.

- **[Risk] Pre-merge cleanup removes files a user intentionally tracked** -> Mitigation: Only clean files matching specific `.wt-tools/` runtime patterns, not the entire directory. Configuration files in `.wt-tools/` (if any) are not affected.

- **[Trade-off] 10-30s added to merge time when lock files conflict** -> Acceptable. Lock file conflicts currently block merges entirely, requiring manual intervention. Automated 30s fix is far better than a blocked pipeline.

## Open Questions

- **Q1:** Should the fallback lockfile-to-PM map in `bin/wt-merge` also cover non-JS ecosystems (e.g., `Gemfile.lock` -> `bundle`, `poetry.lock` -> `poetry`)? The profile system can handle these via `lockfile_pm_map()`, but the hardcoded fallback is JS-only. **Recommendation:** Keep fallback JS-only for now; other ecosystems can use profiles.
