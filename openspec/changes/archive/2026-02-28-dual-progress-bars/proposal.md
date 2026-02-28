## Why

The current usage progress bars show only one dimension: how much of the quota has been consumed. But without seeing how much *time* has elapsed in the window, the user can't judge burn rate at a glance. Adding a time-elapsed bar directly above each usage bar creates an instant visual comparison: if the usage bar is shorter than the time bar, you're on pace; if it's longer, you're burning too fast.

## What Changes

- Replace each single progress bar (5h, 7d) with a **dual bar**: time-elapsed on top, usage on bottom, 0px gap between them
- Time-elapsed bar shows what percentage of the 5h/7d window has passed, calculated from the reset timestamp
- Label format changes from `"45% | 2h 30m"` to two labels: `"60%, 2h"` (time) and `"42%"` (usage), positioned to the left of their respective bars
- Color logic for usage bar changes: green when usage% < time% (under pace), yellow when roughly equal, red when usage% > time% (over pace)

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `usage-display`: Add time-elapsed progress bar above each usage bar; change label format to comma-separated; add burn-rate-relative color coding

## Impact

- `gui/control_center/main_window.py` — layout changes (usage_row doubles from 2 bars to 4 bars + 4 labels), `update_usage_bars()` and `update_usage_bar()` logic
- No new dependencies
- No API changes — time-elapsed % is calculated from existing `session_reset` / `weekly_reset` timestamps
