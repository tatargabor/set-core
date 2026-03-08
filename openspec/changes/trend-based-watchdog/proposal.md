## Why

The per-change token budget system (complexity-based: S=2M, M=5M, L=10M, XL=20M) produces false positives — it kills work that is actually complete or making progress. E2E testing showed all 4 budget-triggered failures were false: the agent had finished its task but the fixed limit fired before the done state could be detected. Fixed limits cannot distinguish between "expensive but productive" and "expensive and wasting tokens." The real signal is whether the agent is making progress, not how much it has spent.

## What Changes

- **Remove** per-change complexity-based token budget enforcement from the watchdog (`_watchdog_check_token_budget`, `_watchdog_token_limit_for_change`, S/M/L/XL defaults)
- **Add** progress-based trend detection to the watchdog that reads Ralph loop-state iterations to detect spinning (no_op) and stuck (no commits) patterns
- **Keep** all existing Ralph-level self-detection (idle, stall, repeated_msg) unchanged
- **Keep** watchdog hash ring + escalation chain unchanged
- **Keep** global orchestrator-level safety nets (token_budget dispatch throttle, token_hard_limit checkpoint trigger)

## Capabilities

### New Capabilities
- `watchdog-progress-detection`: Trend-based progress monitoring that replaces fixed token budgets. Reads completed iterations from loop-state.json to detect spinning (3+ no_op iterations) and stuck (3+ iterations without commits) patterns, triggering pause or fail accordingly.

### Modified Capabilities
- `orchestration-watchdog`: Remove per-change token budget enforcement (R-new), keep all other requirements (R1-R6) unchanged.

## Impact

- `lib/orchestration/watchdog.sh`: Remove `_watchdog_check_token_budget()`, `_watchdog_token_limit_for_change()`, add `_watchdog_check_progress()`. Remove call to budget check in `watchdog_check()`, replace with progress check.
- `lib/orchestration/monitor.sh`: Remove `WATCHDOG_MAX_TOKENS_PER_CHANGE` directive assignment (global token_budget and token_hard_limit remain)
- `lib/loop/engine.sh`: No changes (Ralph self-detection remains)
- Orchestration directives: Per-change complexity defaults no longer used, but `token_budget` and `token_hard_limit` directives remain for global orchestrator-level control
