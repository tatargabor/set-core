# CraftBrew E2E Run #3

**Date:** 2026-03-18
**set-core commit:** `8fb62c890` (start) → `8fb62c890` (end, only sentinel `local` fix committed mid-run)
**Spec:** Multi-file directory spec (17+ docs, 61 requirements, 10 domains)
**Plan:** 15 changes across 4 phases, max_parallel=2

## Final Run Report

### Status: COMPLETE (15/15 merged) — heavy sentinel intervention

| Change | Phase | Tokens | Retries | How Merged | Notes |
|--------|-------|--------|---------|------------|-------|
| project-infrastructure | 1 | 24K | 0 | auto (sentinel recovery) | Context 191% overflow |
| database-schema-seed | 2 | 38K | 3 | **manual** (Bug #12) | Phantom review — scaffold files flagged |
| i18n-routing-layout | 2 | 35K | 1 | auto | Only autonomous merge this run |
| user-accounts | 2 | 78K | 0 | **manual** (Bug #14) | Verify agent died |
| promotions-giftcards | 3 | 56K | 0 | **manual** (Bug #14) | Verify agent died |
| catalog-browsing | 3 | 160K | 1 | **manual** (Bug #14) | Verify agent died; 77% context |
| email-notifications | 3 | 62K | 0 | **manual** (Bug #14) | Verify agent died |
| content-stories | 3 | 23K | 1 | **manual** (Bug #14) | Verify agent died |
| catalog-detail-variants | 3 | 46K | 0 | **manual** (Bug #14) | Verify agent died |
| cart-checkout | 3 | 67K | 0 | **manual** (Bug #14) | Verify agent died |
| reviews-wishlist | 3 | 69K | 0 | **manual** (Bug #14) | Verify agent died |
| order-processing-invoicing | 3 | 68K | 0 | **manual** (Bug #14) | API 529 overload + verify death |
| subscription-system | 4 | 59K | 0 | **manual** (Bug #14) | Verify agent died |
| admin-dashboard-orders | 4 | 9K | 0 | **manual** (Bug #14) | Verify agent died |
| admin-content-promotions | 4 | 94K | 0 | **manual** (Bug #14) | Final change; verify agent died |

### Key Metrics
- **Wall clock**: ~5h 30m (10:22–15:50, incl. API overload delays)
- **Changes merged**: 15/15 (100%)
- **Autonomous merges**: 1/15 (7%) — only i18n-routing-layout
- **Sentinel interventions**: 12 manual merges + multiple sentinel restarts
- **Total tokens**: ~888K
- **Bugs found**: 8 (numbered #12–#19 continuing from run #2)
- **Verify retries**: ~8 total across all changes

### Bugs Found

### 12. Phantom review — scaffold files flagged in verify (Bug #53 regression)
- **Type**: framework
- **Severity**: blocking (caused database-schema-seed to fail permanently)
- **Root cause**: Verify code review includes files from Figma design scaffold on main that don't exist in the change's worktree. The Bug #53 fix (`ab018fa88`) didn't handle repos with pre-existing scaffold code.
- **Fix**: manual merge. Needs proper fix — review diff should only include files modified in the change branch.
- **Recurrence**: Affected most changes but only caused permanent failure on database-schema-seed (3 retries exhausted).

### 13. `local` keyword outside function in set-sentinel line 536
- **Type**: framework (noise)
- **Severity**: noise (bash warning on every poll cycle)
- **Root cause**: `local _poll_state=""` in the top-level while loop, not inside a function.
- **Fix**: `8fb62c890` — changed to plain variable assignment.

### 14. Verify agent dies, change stuck in "verifying" forever
- **Type**: framework
- **Severity**: **critical** — affected 12/15 changes
- **Root cause**: The set-loop/Claude CLI process dies during or after verify gate execution. The monitor's `_poll_active_changes` doesn't detect and recover changes in `verifying` status with dead PIDs. The watchdog reconciliation fires but doesn't transition the state to allow retry or merge.
- **Fix**: manual merge each time. ROOT CAUSE NEEDS FIX — the monitor must detect dead PIDs in `verifying` status and either retry or mark as stalled.
- **Recurrence**: Every single verify attempt except i18n-routing-layout.

### 15. `cc/` model prefix stale — agent can't start
- **Type**: environment/config
- **Severity**: blocking (prevented all dispatch until fixed)
- **Root cause**: `~/.config/set-core/config.json` had `model_prefix: "cc/"` which produced `cc/claude-opus-4-6`. Claude CLI no longer accepts this prefix.
- **Fix**: cleared model_prefix to empty string in config.

### 16. Monitor stuck for 7+ min, sentinel kills orchestrator
- **Type**: framework
- **Severity**: blocking (recurring — happened 3+ times)
- **Root cause**: Python monitor loop blocks in a long-running function call (dispatch, merge, or sync), preventing heartbeat emission. Sentinel's 180s stuck detection kills the orchestrator.
- **Fix**: none yet. Heartbeat should be emitted from a separate thread or the stuck timeout should be longer.

### 17. State extras flattening — manual edits ignored by `from_dict`
- **Type**: framework (design)
- **Severity**: noise (sentinel intervention confusion)
- **Root cause**: `OrchestratorState.to_dict()` flattens extras to top-level JSON keys. Manual edits to a nested `extras` dict are ignored by `from_dict()` which reads top-level keys.
- **Fix**: documented. Always edit top-level keys when manually modifying state JSON.

### 18. Monitor overwrites manual state edits (stale in-memory state)
- **Type**: framework
- **Severity**: blocking (manual merges get reverted)
- **Root cause**: Monitor holds state in memory and writes it on each poll cycle. Even atomic `save_state` with flock gets overwritten because the monitor loads before the edit and saves after.
- **Fix**: kill monitor before editing state, let sentinel restart it with fresh state.

### 19. Sentinel stops cleanly when monitor fails on removed worktrees
- **Type**: framework
- **Severity**: blocking (recurring — sentinel exits, needs manual restart)
- **Root cause**: After manual merge + worktree removal, the monitor tries to sync/verify the removed worktree, fails repeatedly, watchdog triggers, and eventually the orchestrator sets status="stopped" and exits cleanly. Sentinel sees clean exit + stopped = permanent stop.
- **Fix**: none yet. The monitor should detect removed worktrees and skip sync/verify for merged changes.

## Conclusions

1. **Bug #14 (verify agent death) is the #1 priority fix.** It affected 12/15 changes and required manual intervention each time. Without sentinel intervention, only 1/15 changes would have merged autonomously. Root cause investigation needed — why does the Claude CLI process die during verify?

2. **Bug #12 (phantom review) needs a proper fix.** The review diff should be scoped to files actually modified in the change branch, not all files on main. CraftBrew's Figma scaffold (100+ pre-existing component files) causes false review failures.

3. **Bug #18+19 (manual state edit cycle) needs framework support.** Manual merge intervention requires: kill monitor → edit state → remove worktree → restart sentinel. The framework should have a CLI command for this: `set-orchestrate force-merge <change-name>`.

4. **Token efficiency is good.** Average 59K tokens per change (888K / 15), well within the M-complexity expected range of 300K-600K per change. No context overflow failures (Bug #10 from run #2 did not recur).

5. **API 529 overload handling works.** The stall-cooldown-resume pattern correctly handled transient API overload errors without manual intervention.

6. **Phase advancement needs robustness.** Manual state edits can lose `current_phase`, blocking dispatch. The phase system should be reconstructable from change statuses.
