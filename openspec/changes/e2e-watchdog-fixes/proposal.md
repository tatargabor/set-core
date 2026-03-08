## Why

E2E #2 minishop test run (2026-03-08) revealed watchdog false-positive kills and broken token tracking. 4/4 changes merged successfully but with 4 unnecessary WATCHDOG_KILLs and unreliable token counters (products-crud reported 1.4K tokens instead of realistic ~500K+). These issues degrade observability and waste tokens on kill+resume cycles.

## What Changes

- Fix watchdog false-positive kills during artifact creation phase — the watchdog currently escalates L1→L3 in ~30s when loop-state.json doesn't exist yet (artifact creation takes 1-2 min before Ralph loop starts)
- Fix token tracking — orchestrator reads tokens_used from Ralph but the counter stays at 0 or near-0 for some changes
- Add `wt-sentinel` to install.sh scripts list (was missing, causing `command not found`)
- Add `plan_approval: false` bypass for checkpoint in unattended E2E mode

## Capabilities

### New Capabilities
- `watchdog-grace-period`: Watchdog skips hash-based loop detection for newly dispatched changes until loop-state.json appears or a grace period elapses

### Modified Capabilities
- `orchestration-watchdog`: Fix escalation timing for artifact creation phase
- `orchestration-token-tracking`: Fix token counter reads from Ralph loop-state

## Impact

- `lib/orchestration/watchdog.sh` — grace period logic, escalation guard
- `lib/orchestration/monitor.sh` — token tracking reads
- `install.sh` — add wt-sentinel to scripts list
- `bin/wt-orchestrate` — checkpoint auto-approve option
- `tests/e2e/run.sh` — config for unattended mode
