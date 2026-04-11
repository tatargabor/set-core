# Harden E2E Baseline Cache

## Why

`_get_or_create_e2e_baseline` in `modules/web/set_project_web/gates.py` runs the e2e suite on the main checkout and caches the failing test IDs so that later worktree runs can distinguish "real new regressions" from "already broken on main". Investigation (separate from the timeout-masking bug) found four concrete weaknesses in how that cache is produced and consumed:

1. **No locking on cache regeneration.** If two changes both discover a stale cache and both call `_get_or_create_e2e_baseline`, each spawns its own full e2e run on the main checkout. The two runs compete for the same port, the same dev.db file, and race to write the same `e2e-baseline.json` file. The loser's run can corrupt the JSON mid-write or cache partial results. Even with `max_parallel=1` as the norm, checkpoint recovery and future parallelism expose this.

2. **Port collision between worktree run and baseline regeneration.** The worktree e2e call passes `env=e2e_env` with an isolated `PW_PORT` from the profile's port allocator. The baseline regeneration call does NOT pass `env=`, so it inherits the parent process environment — whatever `PW_PORT` the engine was started with, or the most recent worktree's port. If those overlap with a live worktree webServer, the baseline run gets `EADDRINUSE`, falls back to an "infra" failure, and the cache ends up empty (or worse, captures the crash output as "failures").

3. **No dirty-tree check on the project root.** The baseline runs `e2e_command` in the project root (the main worktree). If that directory has uncommitted changes (a half-finished manual edit, a leftover `.env`, or a previous run's artifacts), the baseline captures those effects as part of "main's behavior". Later worktree comparisons are misleading: a failure introduced by main's dirty state is attributed to the change under test.

4. **Main-worktree detection silently falls back to a wrong directory.** `execute_e2e_gate` at `gates.py:401` tries to find the main checkout via `git rev-parse --show-toplevel` + `git worktree list --porcelain`. If both git calls fail (git unreachable, detached worktree, broken `.git` metadata), the fallback is `os.path.dirname(wt_path.rstrip("/"))`. That parent directory is NOT necessarily main — it could be a sibling worktree or an entirely unrelated directory. The baseline then runs somewhere other than main, producing a failure set that has no relation to main's actual behavior.

## What Changes

- **Add file-lock around baseline regeneration** (`fcntl.flock` on a sidecar `.lock` file). Concurrent callers wait for the lock. After acquiring, re-check the cache — if the peer already regenerated for the current `main_sha`, return that instead of spawning another run. All writes use atomic temp-file-plus-rename so partial writes cannot corrupt the JSON.
- **Pass an explicit, dedicated baseline port** in the `env=` argument of the baseline `run_command` call. The port is far from the worktree port-base range (default: `3199`, constant `_E2E_BASELINE_PORT`) so a worktree never shadows it. The profile's `e2e_gate_env` helper is used to build the env dict when available.
- **Skip baseline caching when the project root is dirty.** Before regenerating, call `git status --porcelain` in `project_root`. If the output is non-empty, log a warning, generate the baseline in-memory but do NOT persist it to disk, and attach a `"cacheable": False` flag so the memory result is not returned on later calls.
- **Fail closed when main-worktree detection is unreliable.** `execute_e2e_gate` delegates main-detection to a new helper `_detect_main_worktree(wt_path)` that returns `None` if git calls fail or the fallback parent does not look like a git repository. When detection returns `None`, the gate skips baseline comparison entirely and treats ALL worktree failures as new — the fail-closed direction, never masking real regressions.

Risk 5 (the agent investigation also flagged "stale cache after a fix on main") is NOT addressed here. That one is mitigated by the existing `main_sha` invalidation — when main advances, the cache is regenerated. Remaining edge cases (rebase, branch switch with same SHA) are too rare to justify added invalidation logic and are documented as a known limitation in the design.

## Capabilities

### Modified Capabilities
- `web-gates` — tighten the e2e baseline pipeline: file-lock on regeneration, dedicated port on the baseline run, dirty-tree short-circuit, fail-closed main detection.

## Impact

- **`modules/web/set_project_web/gates.py`**:
  - New module constant `_E2E_BASELINE_PORT = 3199`.
  - New helper `_detect_main_worktree(wt_path: str) -> str | None` — returns the main checkout path or `None` if unreliable.
  - New helper `_is_project_root_clean(project_root: str) -> bool` — runs `git status --porcelain`, returns True if empty.
  - New helper `_baseline_lock_path(baseline_path: str) -> str` — returns the sidecar lock file path.
  - `_get_or_create_e2e_baseline` rewritten with `fcntl.flock` + atomic write + in-memory-only when dirty.
  - `execute_e2e_gate` uses `_detect_main_worktree` — if `None`, skips baseline comparison (fail-closed).
- **Tests**: new `tests/unit/test_e2e_baseline_cache.py` covering: lock acquire + peer regeneration, port isolation assertion, dirty-tree skip-cache, detection failure → no baseline call.
- **Backwards compat**: existing `e2e-baseline.json` files on disk continue to work — the lock file is created next to them on first regeneration. `main_sha` check is unchanged.
- **Risk**: dedicated baseline port `3199` may conflict with a user's existing server. Documented in the `_E2E_BASELINE_PORT` constant comment; users can override via env `SET_E2E_BASELINE_PORT` (future work, not in this change).
