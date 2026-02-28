## 1. Theme Color

- [x] 1.1 Add `bar_time` color to all theme profiles in `gui/constants.py` (light: `#94a3b8`, dark: `#64748b`, gray: `#6b7280`, high_contrast: `#9ca3af`)

## 2. Layout Changes

- [x] 2.1 In `main_window.py`, replace the single usage_row with nested layout: `usage_row > 5h_group (VBox, spacing=0) + 7d_group (VBox, spacing=0)`, each containing a time_row and usage_row (HBox with label + bar)
- [x] 2.2 Create 4 new widgets: `usage_5h_time_label`, `usage_5h_time_bar`, `usage_7d_time_label`, `usage_7d_time_bar` (QLabel bars, height=6px)
- [x] 2.3 Reduce existing `usage_5h_bar` and `usage_7d_bar` height from 8px to 6px
- [x] 2.4 Set fixed width on all 4 labels so bars align vertically within each group

## 3. Time-Elapsed Calculation

- [x] 3.1 Add `calc_time_elapsed_pct(reset_time_str, window_hours)` method to `main_window.py` — computes `(now - (reset - window)) / window * 100`, clamped to 0-100

## 4. Update Logic

- [x] 4.1 Update `update_usage_bars()` to compute time-elapsed % for both 5h (window=5) and 7d (window=168) using the new method
- [x] 4.2 Update time labels to show `"60%, 2h"` format (comma-separated: time_pct, remaining)
- [x] 4.3 Update usage labels to show `"42%"` format (usage_pct only)
- [x] 4.4 Call `update_usage_bar()` for time bars using `bar_time` color (neutral, no burn-rate logic)
- [x] 4.5 Change usage bar color logic from absolute thresholds (90/110%) to burn-rate-relative: green when `usage < time - 5`, yellow when within 5 points, red when `usage > time + 5`

## 5. Fallback States

- [x] 5.1 When no API data: time labels show `"--"`, usage labels show `"--/5h"` / `"--/7d"`, all 4 bars empty
- [x] 5.2 When estimated (no session key): same empty state with tooltips showing token counts

## 6. Tests

- [x] 6.1 Add GUI test in `tests/gui/` covering: dual bar presence, time-elapsed calculation, burn-rate color logic, fallback label states
