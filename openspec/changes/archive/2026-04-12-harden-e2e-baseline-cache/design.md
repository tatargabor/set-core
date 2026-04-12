# Design: Harden E2E Baseline Cache

## Context

`_get_or_create_e2e_baseline` is invoked only when the worktree e2e gate has a non-empty failure list and we want to know which of those failures are already broken on main. The baseline is a pragmatic compromise: rather than enforcing "zero failures on main at all times", it cushions the worktree gate against inherited flakiness. The design assumes a single mutator, a clean main checkout, and a reliable git topology. None of those assumptions are enforced today — this change enforces the first two and fail-closes the third when the assumption breaks.

Reading the current implementation (`gates.py:129-184`):

1. Cache file: `set/orchestration/e2e-baseline.json` (via `SetRuntime().orchestration_dir`).
2. Key: `main_sha` from `git rev-parse HEAD` in `project_root`.
3. Regeneration: runs `e2e_command` in `project_root` with no env, no lock, no cleanliness check; writes the result with a bare `open(..., "w")` followed by `json.dump`.
4. Return value: the cached dict, or `None` on exception (caller's try/except).

The invoking code (`gates.py:401-414`):
1. Computes `project_root = os.path.dirname(wt_path.rstrip("/"))`.
2. Overrides it via `git rev-parse --show-toplevel` + `git worktree list --porcelain` if the git calls succeed.
3. Calls `_get_or_create_e2e_baseline`.
4. Falls through to the "all failures are new" branch if the baseline call raises.

The four weaknesses map cleanly to four fix points. None of them change the cache's semantics (what the cache means); they change how it is produced and when it is trusted.

## Goals / Non-Goals

**Goals:**
- A concurrent caller finds a newly-regenerated baseline instead of racing to regenerate it themselves.
- The baseline run never collides with a live worktree's webServer port.
- A dirty project root does not poison the persistent cache with ephemeral failures.
- A project where git topology cannot be resolved reliably does NOT use a fabricated `project_root` — it skips baseline entirely and treats everything as new.

**Non-Goals:**
- Eliminating the baseline concept. Baseline comparison has genuine value for projects with inherited flakiness — it makes the signal actionable.
- Detecting "this test was flaky in baseline but is now a real regression". That needs per-test history, not per-run caching, and is a larger design.
- Runtime-configurable baseline port. The constant `_E2E_BASELINE_PORT = 3199` is hardcoded for simplicity; override via env var is future work.
- Locking the baseline cache across processes on different machines (shared NFS storage). `fcntl.flock` is local-machine only, which is fine for the orchestrator's actual deployment.

## Decisions

### 1. `fcntl.flock(LOCK_EX)` on a sidecar `.lock` file

**Choice:** When regeneration is needed, open `e2e-baseline.json.lock` for writing, call `fcntl.flock(fd, fcntl.LOCK_EX)`, then proceed. While the lock is held, re-read the cache file and re-check `main_sha` — if a peer already regenerated for the current SHA, return the peer's result. Write the new cache via atomic temp-file + `os.rename`.

**Why `fcntl.flock` and not `filelock` / `portalocker`?** Python's `fcntl` is stdlib, works on Linux and macOS (the orchestrator's target platforms), and requires no new dependency. Windows support is not a concern for set-core. Additional dependencies would add install friction for a single lock point.

**Why re-check after acquiring the lock?** The second caller might wait 60-120s for the first caller's baseline run. After the lock releases, the cache on disk is current. Re-reading avoids spawning a second full e2e run for nothing.

**Why atomic temp-file-plus-rename?** `open(path, "w")` truncates immediately then writes line-by-line. If the process dies mid-write, the cache is half-written JSON. `tempfile.NamedTemporaryFile` + `os.rename` is atomic on the same filesystem — either the old cache is there, or the new one, never a partial.

### 2. Dedicated baseline port via explicit env dict

**Choice:** Define `_E2E_BASELINE_PORT = 3199` as a module constant. When the baseline run_command is called, build an env dict with `PW_PORT = "3199"` (plus whatever `profile.e2e_gate_env(3199)` adds, such as `DATABASE_URL` or feature flags). Pass that env dict to `run_command(env=e2e_env_baseline)`.

**Why 3199?** The worktree port allocator defaults to `e2e_port_base = 3100` and allocates `3100 + change_index`. 3199 is the far end of that range — unlikely to collide with a normal worktree port but still in the "dev range" that firewalls and ports-lists typically allow. If the user's base is ≥ 3200, this is free.

**Why not let the user configure it?** Adds config surface area for a corner case. Future extension: read `SET_E2E_BASELINE_PORT` env var if set, fall back to the constant. Out of scope now.

### 3. Dirty project root → in-memory-only baseline

**Choice:** Before regeneration, run `git status --porcelain` in `project_root`. If the output is non-empty, log a WARNING, run the baseline anyway (we still need SOMETHING for the comparison), but do NOT write it to disk and mark the returned dict with `"cacheable": False`.

**Why not skip baseline entirely when dirty?** A legitimate case: the user is iterating on the main checkout while orchestration runs. Their dirty state probably doesn't affect e2e tests. Skipping would force every wt comparison to "treat as new failures" — too aggressive for an edit-in-progress situation. The compromise: use the baseline for THIS gate call, then throw it away.

**Why mark the dict instead of just not writing the file?** A subsequent call that hits the not-written state would re-run baseline. The mark is a signal for the caller, not for control flow — lets future extensions (e.g., dashboard warning) see that the baseline was not cached.

### 4. `_detect_main_worktree` returns `None` on uncertainty → skip baseline

**Choice:** Extract the main-worktree-detection logic into `_detect_main_worktree(wt_path: str) -> str | None`. Returns the main checkout path if both git calls succeed and the result is a valid directory with a `.git` entry (file or directory). Returns `None` otherwise.

In `execute_e2e_gate`, if `_detect_main_worktree(wt_path)` returns `None`, skip the `_get_or_create_e2e_baseline` call entirely and proceed as if `baseline is None` — the existing "all failures are new" branch handles that correctly.

**Why fail-closed?** The worst failure mode of the current code is to run the baseline in a wrong directory (e.g. the worktree root's parent, which might be another worktree or `/tmp`) and get a garbage failure set. That garbage set then either masks real regressions (false PASS) or invents new ones (false FAIL). Fail-closed is strictly better: real regressions always surface.

**Why not use `os.path.dirname` as a last-ditch fallback?** That's the current behavior that is being removed. A "probably right" fallback is worse than no fallback, because it looks correct while being wrong.

## Risks / Trade-offs

- **[Risk] `fcntl.flock` does not work on NFS.** Mitigation: the orchestrator runs on local disk in all known deployments. Document the assumption.
- **[Risk] Dirty project root is common during development.** Mitigation: WARNING log, in-memory-only baseline still runs — no behavioral difference for the gate, just more frequent re-generation. Cost is bounded by e2e runtime.
- **[Risk] `3199` collides with someone's service.** Mitigation: constant is documented; override path is clear (env var in a future follow-up). Unlikely to be a real problem — the port is only bound during the baseline run itself (~2-3 minutes).
- **[Trade-off] Fail-closed main detection means some valid-but-weird topologies lose baseline comparison.** Accepted — the alternative (running in the wrong directory) is strictly worse. Users with exotic setups can force baseline regeneration by setting an env var (future work) or run in a normal git worktree.
- **[Trade-off] Re-reading the cache after acquiring the lock adds one extra stat + open per concurrent caller.** Negligible — milliseconds per call.

## Verification Plan

- **Unit test — lock acquire + peer regeneration**: write a baseline file with `main_sha = X`, simulate a lock holder by creating the sidecar lock file manually, call `_get_or_create_e2e_baseline` and assert it waits or re-reads. (Threaded test may be flaky; prefer a deterministic mock.)
- **Unit test — atomic write**: monkeypatch `json.dump` to raise mid-write, assert the cache file is either the old content or completely absent (never partial).
- **Unit test — port isolation**: monkeypatch `run_command` to capture the `env` argument, assert `env["PW_PORT"] == "3199"`.
- **Unit test — dirty tree**: monkeypatch `run_git` to return a non-empty `git status --porcelain`, call `_get_or_create_e2e_baseline`, assert no file was written AND a WARNING was logged AND the returned dict has `cacheable == False`.
- **Unit test — main detection failure**: monkeypatch `run_git` to fail, call `execute_e2e_gate` with real failure output, assert `new_failures` contains ALL the failure IDs (not filtered by a bogus baseline).
- **Regression check**: run the existing `tests/unit/test_gate_e2e_timeout.py` to ensure nothing else broke.
