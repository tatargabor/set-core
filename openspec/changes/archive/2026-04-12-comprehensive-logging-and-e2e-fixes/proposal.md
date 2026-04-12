# Change: comprehensive-logging-and-e2e-fixes

## Why

The orchestration pipeline has ~100 remaining silent failure points where errors, missing data, fallbacks, and skipped steps produce no log output. Three critical subsystems are broken silently:

1. **Two-phase E2E gate never fires** — `_detect_own_spec_files()` uses `git merge-base` which is trivial post-integration-merge, and the e2e-manifest.json fallback has predicted (wrong) filenames
2. **Coverage gate silently skips** — `SetRuntime().digest_dir` resolves to the wrong path (system runtime dir, not project-local digest)
3. **Python logger output is invisible** — goes to journalctl/stderr only, not to events.jsonl or dashboard

Additional gaps found by audit:
- 25 `except Exception: pass` blocks that swallow errors completely
- 15 `except + logger.debug()` that are effectively silent (debug disabled in production)
- 50 functions returning empty/None/[] without explaining why
- 40 `os.path` checks where the negative path has no log
- 7 `load_profile()` calls without passing project path
- Gate executors (build/test/e2e/review) log no input parameters

## What Changes

### 1. Universal DEBUG logging for all return paths

Every function that returns empty/None/False/[] gets a `logger.debug()` explaining why. Default log level is DEBUG so these are always visible. Config can raise to INFO/WARNING.

### 2. SetRuntime() elimination

Replace all `SetRuntime().digest_dir` calls with `state_file`-relative path resolution. Three remaining instances in merger.py and engine.py.

### 3. `_detect_own_spec_files` rewrite

Replace git merge-base approach with worktree-vs-main file comparison (`git ls-tree main tests/e2e/` vs `os.listdir`). Add manifest validation (check actual file existence). Log every detection step.

### 4. Coverage gate digest_dir fix

Same pattern as engine.py fix: use `os.path.dirname(state_file)` + `set/orchestration/digest/`.

### 5. Except handler upgrade

All `except Exception: pass` → at minimum `logger.debug()`. All `except + logger.debug()` on fallback paths → `logger.warning()`.

### 6. Gate executor entry/exit logging

Every gate executor logs: `Gate[name] START change=%s wt=%s cmd=%s` and `Gate[name] END change=%s result=%s elapsed=%dms`.

### 7. Bash script logging

Shell scripts (set-orchestrate, set-merge, set-new) get consistent `log_info`/`log_warn` calls at decision points.

### 8. Sentinel log awareness

Sentinel skill prompt updated to: scan logs for `[ANOMALY]` and `WARNING`, investigate root causes, and add missing logging when fixing bugs.

## Out of Scope

- Structured JSON logging format (current text format is fine)
- Log aggregation infrastructure
- Event bus integration for all log points (future change)
- Log rotation or size limits
