# CraftBrew E2E — Run #1

**Date**: 2026-03-15 ~ 2026-03-16 (overnight)
**wt-tools commit**: 58f63afa2 (master)
**Project dir**: `/tmp/craftbrew-run1`
**Spec**: CraftBrew multi-file spec (15 changes, 5 phases, 50 REQs, 10 domains)

## Bugs Found

### 1. PyYAML not available in linuxbrew Python 3.14
- **Type**: framework (non-blocking)
- **Severity**: noise
- **Root cause**: `wt-orch-core` runs under linuxbrew Python 3.14 which doesn't have PyYAML. `profile_loader.py` falls back to NullProfile.
- **Fix**: N/A — fallback works, just a warning in logs
- **Recurrence**: known, not worth fixing

### 2. Stall detection during initial dispatch
- **Type**: framework
- **Severity**: noise (auto-recovers)
- **Root cause**: Agent dispatched to worktree, starts working but initial commits are doc-only (README, config). Stall detector flags as "no implementation progress".
- **Fix**: Stall cooldown (300s) allows recovery automatically. Working as designed.
- **Recurrence**: expected pattern

### 3. Figma MCP blocks claude -p mode
- **Type**: framework (blocking)
- **Severity**: blocking
- **Root cause**: Figma HTTP MCP (`https://mcp.figma.com/mcp`) requires interactive OAuth browser auth. When registered in `.claude/settings.json`, `claude -p` (pipe mode) hangs indefinitely waiting for auth.
- **Fix**: `ee8529342` — removed Figma MCP registration from both E2E scaffold scripts. Design data available via static `design-snapshot.md` + `figma-raw/` files.
- **Deployed**: yes
- **Recurrence**: new

### 4. Python monitor crashes with JSONDecodeError on sentinel restart
- **Type**: framework (blocking)
- **Severity**: blocking
- **Root cause**: Bash dispatcher creates directives via `mktemp /tmp/orch-directives-XXXXXX.json`. On sentinel restart, a new bash process creates a NEW temp file, but the old path (stored nowhere) is gone. The Python monitor receives the deleted file path via `--directives`, `os.path.isfile()` returns False, falls through to `json.loads(path_string)` which crashes: `JSONDecodeError: Expecting value`.
- **Compound issue**: Python's atexit handler sets `status="stopped"`. Sentinel sees `exit_code=1 + status=stopped` → `is_transient_failure` returns true (exit_code != 0) → restarts → same crash → 5 rapid crashes → sentinel gives up.
- **Fix**: `58f63afa2` — two changes:
  1. `dispatcher.sh`: use stable path `wt/orchestration/directives.json` instead of `mktemp`
  2. `engine.py` + `cli.py`: fall back to directives persisted in state file when file is missing
- **Deployed**: yes
- **Recurrence**: new

### 5. Sentinel kills monitor during stall cooldown (heartbeat too slow)
- **Type**: framework (blocking)
- **Severity**: blocking
- **Root cause**: Monitor emits WATCHDOG_HEARTBEAT every 20 polls (20*15s = 300s). Sentinel stuck timeout is 180s. During stall recovery, the monitor waits for the 300s cooldown without writing to the state file or events — sentinel sees no activity for 180s and kills it.
- **Fix**: `b1b5d1a29` — reduce heartbeat interval to every 8 polls (8*15s = 120s), well within the 180s threshold.
- **Deployed**: yes
- **Recurrence**: new (existed latently, first triggered by stall + no other activity)

### 6. Verify gate fails on untracked files without auto-commit
- **Type**: framework (blocking)
- **Severity**: blocking
- **Root cause**: Agent created `.eslintignore` and `.prettierignore` but didn't `git add` them. Verify gate detects "2 untracked" and retries 3x — but retries just re-check the same dirty worktree without re-running the agent (which already exited). Guaranteed 3x failure.
- **Fix**: `06e3cce60` — verify gate now auto-commits leftover files (`git add -A && git commit`) before checking. Only fails if worktree is STILL dirty after auto-commit.
- **Deployed**: yes
- **Recurrence**: new (previous runs had this issue masked by other failures)

### 7. UnicodeDecodeError on binary subprocess output
- **Type**: framework (blocking)
- **Severity**: blocking
- **Root cause**: `subprocess_utils.run_command()` uses `subprocess.run(text=True)` which defaults to strict UTF-8 decoding. When a subprocess emits binary data (e.g. PNG screenshot bytes, `0x89` header), the decode crashes with `UnicodeDecodeError`. This caused the monitor to stall after merging `subscription-management` — the post-merge smoke test captured screenshot binary in stdout, and the watchdog recovery loop couldn't escape.
- **Fix**: `cf0753258` — add `errors="replace"` to `subprocess.run()` call so invalid bytes are substituted with `U+FFFD` instead of crashing.
- **Deployed**: yes
- **Recurrence**: new (first triggered when post-merge smoke test captured screenshots)

### 8. Verify gate stuck in "verifying" — spec_verify crash leaves status orphaned
- **Type**: framework (blocking)
- **Severity**: blocking
- **Root cause**: `handle_change_done()` crashes during Step 5b/6 (rules/spec_verify) — likely `render_review_template` failure (sentinel log: "Failed to render review template for X"). The exception is caught by `_poll_active_changes` generic handler (`except Exception: logger.warning`), but the change status remains `"verifying"` indefinitely. On next poll, `poll_change()` sees status=verifying + loop_state=done → calls `handle_change_done()` again → same crash → infinite loop with no progress.
- **Compound issue**: Dirty main working tree (leftover file modifications from previous merges) causes `wt-merge` to fail with "no conflict markers" — even after the status is manually advanced to `done`.
- **Fix**: Manual intervention required (both reviews-wishlist and admin-panel). For a proper fix: `handle_change_done` should catch exceptions in the spec_verify step and fall through to merge rather than leaving status stuck. Also, main working tree should be cleaned before merge attempts.
- **Deployed**: not yet (manual workaround applied)
- **Recurrence**: new — hit on both Phase 5 changes

## Timeline

| Time | Event |
|------|-------|
| ~22:30 | Scaffold script run, project created |
| ~22:35 | Sentinel started, planning + decomposition |
| ~22:50 | Planning complete: 15 changes, 5 phases |
| ~22:55 | First dispatch: test-infrastructure-setup |
| ~23:10 | Bug #3 discovered: Figma MCP blocking agent |
| ~23:20 | Bug #3 fixed, restarted |
| ~23:30 | Bug #4 discovered: JSONDecodeError crash loop |
| ~00:27 | Bug #4 fixed, restarted successfully |
| ~00:27 | Orchestration running, test-infrastructure-setup dispatched |
| ~00:31 | Bug #5: sentinel kills monitor (heartbeat too slow) |
| ~00:33 | Bug #5 fixed, deployed, restarted |
| ~00:43 | test-infrastructure-setup reaches verify gate |
| ~00:44 | Bug #6: verify fails 3x on untracked files |
| ~01:05 | Bug #6 fixed, change reset to pending |
| ~01:13 | Orchestration resumed, Phase 1-3 progressing |
| ~03:55 | subscription-management merged (7th merge), monitor stalls |
| ~04:03 | Bug #7 discovered: UnicodeDecodeError in subprocess output |
| ~04:03 | Bug #7 fixed, sentinel restarted |
| ~04:10 | Orchestration resumed, Phase 3-4 progressing |
| ~05:16 | checkout-flow merged (11th) |
| ~05:39 | checkout-returns merged (12th) |
| ~05:40 | Phase 5 dispatched: reviews-wishlist + email-notifications |
| ~06:06 | email-notifications merged (13th) |
| ~06:11 | reviews-wishlist all gates pass, stuck in verifying (Bug #8) |
| ~06:20 | Bug #8 manual fix: advance to done, clean main tree, merge |
| ~06:22 | admin-panel dispatched (last change) |
| ~06:35 | admin-panel implementing (224K tokens) |
| ~07:20 | admin-panel build:fail, retry #1 dispatched |
| ~07:30 | admin-panel build:pass, test:fail, retry #2 dispatched |
| ~07:46 | admin-panel all gates pass (build+test+review), stuck in verifying (Bug #8 again) |
| ~07:48 | Bug #8 manual fix: advance to done, merge (fast-forward) |
| ~07:48 | **15/15 MERGED — Run complete** |

## Final Results

**Outcome**: 15/15 changes merged, 0 failed
**Wall clock**: ~9h 18m (22:30 → 07:48)
**Active time**: ~5h 45m (excluding bug fix downtime ~3h 33m)
**Total tokens**: 11,043,614 (11.0M)
**Total tests**: 298 passing (final main state)

### Per-Change Metrics

| Change | Phase | Tokens | Tests | Build | Test | Review | Retries |
|--------|-------|--------|-------|-------|------|--------|---------|
| test-infrastructure-setup | 1 | 8K | — | — | skip | pass | 0 |
| database-schema-seed | 1 | 537K | 13 | pass | pass | pass | 2 |
| user-auth-core | 2 | 1,025K | 31 | pass | pass | pass | 0 |
| catalog-browsing | 2 | 1,099K | 67 | pass | pass | pass | 1 |
| content-stories | 3 | 677K | 56 | pass | pass | pass | 0 |
| user-account-profile | 3 | 644K | 85 | pass | pass | pass | 2 |
| promo-engine | 3 | 568K | 91 | pass | pass | pass | 0 |
| subscription-management | 3 | 1,023K | 167 | pass | pass | pass | 2 |
| catalog-search-filters | 3 | 720K | 175 | pass | pass | pass | 0 |
| cart-core | 3 | 701K | 167 | pass | pass | pass | 0 |
| checkout-flow | 4 | 1,323K | 236 | pass | pass | pass | 2 |
| checkout-returns | 4 | 606K | 252 | pass | pass | pass | 0 |
| email-notifications | 5 | 529K | 270 | pass | pass | pass | 0 |
| reviews-wishlist | 5 | 711K | 280 | pass | pass | pass | 1 |
| admin-panel | 5 | 873K | 298 | pass | pass | pass | 2 |

### Bug Summary

| # | Description | Severity | Fixed | Sentinel interventions |
|---|-------------|----------|-------|----------------------|
| 1 | PyYAML not in linuxbrew Python 3.14 | noise | N/A | 0 |
| 2 | Stall detection during initial dispatch | noise | by design | 0 |
| 3 | Figma MCP blocks claude -p mode | blocking | ee85293 | 1 |
| 4 | Monitor JSONDecodeError on restart | blocking | 58f63af | 1 |
| 5 | Sentinel kills monitor (heartbeat too slow) | blocking | b1b5d1a | 1 |
| 6 | Verify gate fails on untracked files | blocking | 06e3cce | 1 |
| 7 | UnicodeDecodeError on binary subprocess output | blocking | cf07532 | 1 |
| 8 | Verify gate stuck in "verifying" (spec_verify crash) | blocking | manual | 2 |

**Total sentinel/manual interventions**: 7 (5 automated fix+restart, 2 manual merge assists)
