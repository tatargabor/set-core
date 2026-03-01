## Why

The token status bar in wt-control has two UX issues: (1) the dual stripe bar shows time-elapsed on top and usage on bottom, but usage percentage is the primary information — it should be on top for visual priority, (2) the 3-level burn rate coloring (green/amber/red with ±5% tolerance) is harder to parse at a glance than a simple binary: green = under budget, red = over budget. Additionally, the usage worker has zero logging in its run loop, making freeze debugging impossible.

## What Changes

- **Swap stripe order** in DualStripeBar: usage (%) on top, time elapsed on bottom
- **Simplify usage stripe color**: binary green (usage < time) / red (usage >= time), removing amber middle zone
- **Change time stripe color**: from blue (`#60a5fa`) to light gray (`#d1d5db`) — time is secondary info
- **Add debug logging** to UsageWorker run loop: poll start/end, API attempt results, sleep cycles

## Capabilities

### New Capabilities

### Modified Capabilities
- `token-status-bar`: Swap stripe rendering order, simplify burn rate color logic, change time stripe color to gray
- `usage-worker-logging`: Add debug-level logging to UsageWorker run loop for freeze diagnosis

## Impact

- `gui/widgets/dual_stripe_bar.py` — stripe paint order swap
- `gui/control_center/main_window.py` — `_burn_rate_color()` simplification, `set_values()`/`set_colors()` argument order, time color constant
- `gui/constants.py` — `bar_time` color value change
- `gui/workers/usage.py` — debug log statements in `run()` loop
