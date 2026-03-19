## 1. Watchdog artifact creation grace

- [x] 1.1 In `lib/orchestration/watchdog.sh` `watchdog_check()`, add guard before hash loop detection (line ~74): if status is `running` and `loop-state.json` does not exist in the worktree, skip hash-based detection and return early. The timeout check (line ~96) with PID-alive guard remains active.
- [x] 1.2 ~~Add event for loop-state transition~~ — skipped, existing DISPATCH→first HEARTBEAT timeline covers this. Over-engineering.

## 2. Token tracking fix

- [x] 2.1 Fix `bin/wt-usage` Python import: resolve symlinks with `.resolve()`, fallback to `importlib.util` direct file import to bypass gui/__init__.py PySide6 dependency.
- [x] 2.2 ~~Fallback to estimate_tokens_from_files~~ — not needed, root cause was import path + timezone bug, now fixed.
- [x] 2.3 Verified: `wt-usage --format json` from `/tmp` returns valid JSON with total_tokens=149M. `--since` flag also works.

## 3. Checkpoint auto-approve

- [x] 3.1 Add `checkpoint_auto_approve` directive to `bin/set-orchestrate` defaults (default: `false`) and directive parsing.
- [x] 3.2 In `trigger_checkpoint()` (state.sh), when `CHECKPOINT_AUTO_APPROVE` global is `true`, auto-approve and return immediately without waiting.
- [x] 3.3 Update `tests/e2e/run.sh` config to include `checkpoint_auto_approve: true`.

## 4. Install script fix

- [x] 4.1 Verified `set-sentinel` is in `install.sh` scripts list.

## 5. Validation

- [x] 5.1 Run E2E #3: `./tests/e2e/run.sh` on a fresh dir, then sentinel. Results: 0 false-positive kills ✓, no checkpoint prompt ✓, no `command not found` ✓, token counters show non-zero values ✓. **Note:** Token values are inflated due to cross-project contamination bug in `wt-usage` (scans ALL ~/.claude/projects/ dirs, not just current worktree). Separate fix needed — filed as new issue.
