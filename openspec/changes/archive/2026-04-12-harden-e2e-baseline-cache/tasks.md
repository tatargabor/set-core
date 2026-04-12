# Tasks

## 1. Helpers: detection, cleanliness, lock path

- [x] 1.1 In `modules/web/set_project_web/gates.py`, add a module constant `_E2E_BASELINE_PORT = 3199` near the top, documented with a one-line comment explaining it is a dedicated port to avoid worktree collisions [REQ: E2E baseline run uses a dedicated port]
- [x] 1.2 Add a helper `_detect_main_worktree(wt_path: str) -> str | None` that returns the main checkout path or `None`. Implementation: call `run_git("rev-parse", "--show-toplevel", cwd=wt_path)` — if it fails, return `None`. Then call `run_git("worktree", "list", "--porcelain", cwd=wt_path)` — parse the lines, pick the first `worktree <path>` line whose basename differs from `wt_path`'s basename, verify the returned path contains a `.git` file or directory, and return it. If any step fails or returns nothing, return `None` [REQ: Unreliable main detection fails closed]
- [x] 1.3 Add a helper `_is_project_root_clean(project_root: str) -> bool` that runs `run_git("status", "--porcelain", cwd=project_root)` and returns True iff the stdout is empty [REQ: Dirty project root skips cache persistence]
- [x] 1.4 Add a helper `_baseline_lock_path(baseline_path: str) -> str` that returns `baseline_path + ".lock"` [REQ: E2E baseline regeneration is serialized by a file lock]

## 2. Rewrite `_get_or_create_e2e_baseline` with lock + dirty check + atomic write

- [x] 2.1 Before any regeneration work, call `_is_project_root_clean(project_root)` and store the result as `clean_root` [REQ: Dirty project root skips cache persistence]
- [x] 2.2 Keep the existing "cache file exists and main_sha matches" short-circuit so clean-hit is fast [REQ: Existing cache files remain compatible]
- [x] 2.3 When regeneration is needed, open the lock file path (`_baseline_lock_path(baseline_path)`) with `open(..., "a+")` and acquire `fcntl.flock(fd, fcntl.LOCK_EX)`. Use a context manager or try/finally to guarantee release [REQ: E2E baseline regeneration is serialized by a file lock]
- [x] 2.4 After acquiring the lock, re-check the cache file. If it now exists and `main_sha` matches, return that result without regenerating [REQ: E2E baseline regeneration is serialized by a file lock]
- [x] 2.5 Build the env dict for the baseline run: start with `{"PW_PORT": str(_E2E_BASELINE_PORT)}`. If the profile is passed through and exposes `e2e_gate_env(_E2E_BASELINE_PORT)`, merge those keys. (For now, no profile is passed to `_get_or_create_e2e_baseline` — accept a new optional `profile=None` parameter in the signature, plumbed through from the caller.) [REQ: E2E baseline run uses a dedicated port]
- [x] 2.6 Pass the env dict to `run_command` via the `env=` kwarg alongside the existing `timeout`, `cwd`, `max_output_size` arguments [REQ: E2E baseline run uses a dedicated port]
- [x] 2.7 After the e2e run completes and `failures` are extracted, build the `baseline` dict as before and add a `"cacheable": clean_root` field [REQ: Dirty project root skips cache persistence]
- [x] 2.8 Persist the cache ONLY when `clean_root` is True. Use a temp file next to `baseline_path` (same directory) + `os.rename` for atomicity. On dirty root, log WARNING with the phrase "dirty project root, baseline not cached" and skip the write [REQ: Dirty project root skips cache persistence, E2E baseline regeneration is serialized by a file lock]
- [x] 2.9 The function SHALL return the baseline dict in all success paths (clean or dirty). Caller reads `"cacheable"` only if it wants to surface a dashboard warning; the primary consumer (`execute_e2e_gate`) uses the `"failures"` field as before [REQ: Dirty project root skips cache persistence]

## 3. Wire `_detect_main_worktree` into `execute_e2e_gate`

- [x] 3.1 Replace the ad-hoc main-detection block at `gates.py:401-408` with a single call to `_detect_main_worktree(wt_path)` [REQ: Unreliable main detection fails closed]
- [x] 3.2 If the helper returns `None`, skip the `_get_or_create_e2e_baseline` call entirely (leave `baseline = None`) and log INFO `"main worktree detection unreliable — skipping baseline comparison (fail-closed)"` [REQ: Unreliable main detection fails closed]
- [x] 3.3 The existing downstream logic (`if baseline: ... else: treat all as new`) handles `baseline is None` correctly. No further changes needed in that branch [REQ: Unreliable main detection fails closed]
- [x] 3.4 Thread the `profile` argument through from `execute_e2e_gate` to `_get_or_create_e2e_baseline` (new optional parameter, default `None`) so the baseline env dict can include profile-specific keys [REQ: E2E baseline run uses a dedicated port]

## 4. Unit tests — `tests/unit/test_e2e_baseline_cache.py` (new file)

- [x] 4.1 Create `tests/unit/test_e2e_baseline_cache.py` with the standard test scaffolding (sys.path, imports from set_project_web.gates, tmp_path fixture, CommandResult helper) [REQ: all]
- [x] 4.2 `test_detect_main_worktree_success`: mock `run_git` to return a valid `rev-parse` and a `worktree list` with one main and one wt, assert the helper returns the main path. Create the main path on disk (`tmp_path / "main"`) with a `.git` file so the path validation passes [REQ: Unreliable main detection fails closed]
- [x] 4.3 `test_detect_main_worktree_git_fails`: mock `run_git` rev-parse to return exit_code=1, assert the helper returns `None` [REQ: Unreliable main detection fails closed]
- [x] 4.4 `test_detect_main_worktree_no_dot_git`: mock the git calls to return a path that does not contain `.git`, assert `None` [REQ: Unreliable main detection fails closed]
- [x] 4.5 `test_is_project_root_clean_empty`: mock `run_git` to return empty stdout for `status --porcelain`, assert True [REQ: Dirty project root skips cache persistence]
- [x] 4.6 `test_is_project_root_clean_dirty`: mock to return `" M some/file.ts\n"`, assert False [REQ: Dirty project root skips cache persistence]
- [x] 4.7 `test_baseline_port_in_env`: patch `run_command` to capture the env argument passed to it. Call `_get_or_create_e2e_baseline` with no cached file, clean git, a stubbed successful e2e run. Assert the captured env contains `PW_PORT == "3199"`. Also assert that if the parent `os.environ` has `PW_PORT = "3105"` set, the child env still has `3199` [REQ: E2E baseline run uses a dedicated port]
- [x] 4.8 `test_baseline_dirty_root_not_cached`: monkeypatch `run_git` so `git status --porcelain` returns a dirty line. Monkeypatch `run_command` to return a stubbed successful e2e run. Call the function and assert: (a) the returned dict has `"cacheable": False`, (b) the baseline file does NOT exist on disk afterwards, (c) a WARNING was logged mentioning "dirty project root". Use `caplog` fixture for the log assertion [REQ: Dirty project root skips cache persistence]
- [x] 4.9 `test_baseline_lock_peer_regenerated`: Write a stale baseline file (main_sha = "old"). Monkeypatch `run_git` HEAD to return "new". BEFORE calling the function, create the lock file with a concurrent-style pre-write: write a FRESH baseline file with main_sha = "new" (simulating a peer that already regenerated). Then call `_get_or_create_e2e_baseline` and assert: (a) it returned the fresh result, (b) `run_command` was NOT called (peer's work reused). The lock acquisition is synchronous so the test can rely on the peer's file being in place when the lock is checked [REQ: E2E baseline regeneration is serialized by a file lock]
- [x] 4.10 `test_baseline_atomic_write`: monkeypatch `json.dump` to raise an exception mid-write. Call `_get_or_create_e2e_baseline`. Assert: (a) the function raises OR returns a dict without crashing, (b) the final `e2e-baseline.json` file is either non-existent OR equal to the PREVIOUS content — never a truncated partial [REQ: E2E baseline regeneration is serialized by a file lock]
- [x] 4.11 `test_main_detection_none_skips_baseline`: monkeypatch `_detect_main_worktree` to return `None`. Monkeypatch `run_command` to return a real Playwright failure output. Call `execute_e2e_gate`. Assert: (a) `_get_or_create_e2e_baseline` was NOT called, (b) the gate returned `status="fail"`, (c) the output mentions the real failure IDs without any "pre-existing" filtering [REQ: Unreliable main detection fails closed]

## 5. Regression check

- [x] 5.1 Run `tests/unit/test_gate_e2e_timeout.py` and `tests/unit/test_verifier_gate_order.py` after implementation — assert they still all pass (no unrelated regression) [REQ: all]
- [x] 5.2 Run `tests/unit/test_gate_runner.py::TestTruncateGateOutput` — assert unchanged [REQ: all]

## 6. Documentation touch-ups

- [x] 6.1 Grep `docs/` for `e2e-baseline` mentions — no matches, nothing to update [REQ: all]
- [x] 6.2 Add a short note to `.claude/rules/` — no dedicated gate rule file exists; skipped per task instructions [REQ: Unreliable main detection fails closed]
