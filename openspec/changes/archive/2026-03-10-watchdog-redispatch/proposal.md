## Why

When a Ralph loop gets stuck (3+ no-progress iterations, hash loop, or timeout), the watchdog currently escalates to kill + `failed` status. The change is lost and requires either manual intervention or a full replan cycle. Production evidence (MiniShop admin-auth: 3x manual restart, sales-raketa stalls) shows this is the #1 source of wasted tokens and human intervention during orchestration runs. Inspired by ruflo's work-stealing pattern, we can automatically re-dispatch stuck changes to fresh worktrees with clean context, dramatically reducing manual interventions.

## What Changes

- Watchdog L3 escalation changes from "kill + resume" to "kill + cleanup + re-dispatch to fresh worktree"
- New `redispatch_change()` function in dispatcher.sh that tears down the old worktree and dispatches the change fresh
- New `redispatch_count` field on each change in state.json, with configurable `max_redispatch` limit (default: 2)
- L3 escalation (after max redispatches exhausted) remains "fail" as final fallback
- Status output and event logging updated to reflect redispatch activity
- Retry context from the failed attempt is carried forward so the fresh agent knows what didn't work

## Capabilities

### New Capabilities
- `watchdog-redispatch`: Automatic re-dispatch of stuck changes to fresh worktrees with escalation limits and failure context forwarding

### Modified Capabilities
- `orchestration-watchdog`: L3 escalation behavior changes from kill+resume to kill+redispatch

## Impact

- **Code**: `lib/orchestration/watchdog.sh` (escalation logic), `lib/orchestration/dispatcher.sh` (new redispatch function), `lib/orchestration/state.sh` (new fields), `lib/orchestration/monitor.sh` (status display)
- **Config**: New directive `max_redispatch` in orchestration.yaml
- **Behavior**: Stuck changes get a second (and third) chance automatically instead of requiring human intervention
- **Tokens**: Slight increase per-change (redispatch costs ~50-100K tokens for fresh start), but overall decrease by eliminating replan cycles (~500K+ tokens)
