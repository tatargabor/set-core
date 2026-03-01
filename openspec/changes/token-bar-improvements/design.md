## Context

The wt-control TUI has a token usage status bar showing dual-stripe progress bars (DualStripeBar widget) per account. Currently: time-elapsed on top (blue), usage consumed on bottom (green/amber/red based on burn rate). The label format is `"3h12m · 45%"`. The usage worker that feeds this data has no debug logging in its run loop, making freeze diagnosis impossible.

## Goals / Non-Goals

**Goals:**
- Swap stripe order so usage % (primary info) is visually on top
- Simplify burn rate coloring to binary green/red (under/over budget)
- Make time stripe visually subdued (light gray instead of blue)
- Add debug logging to usage worker for operational visibility

**Non-Goals:**
- Changing the label text format (remains `"time · pct%"`)
- Changing the DualStripeBar widget height (stays 10px)
- Changing the usage worker polling interval (stays 30s)
- Adding usage worker retry/recovery logic (separate concern)

## Decisions

### 1. Stripe order: usage on top, time on bottom
**Rationale**: Usage percentage is the actionable metric — "am I burning too fast?" Time elapsed is context. Top position = first thing the eye reads.

**Implementation**: Swap the two `fillRect` calls in `DualStripeBar.paintEvent()`. The variables stay the same (`_time_pct`, `_usage_pct`), only their y-positions swap. Also swap the argument order in `set_values()` calls from main_window.py so the semantics remain correct.

### 2. Binary green/red instead of 3-level burn rate
**Rationale**: The ±5% amber tolerance zone adds cognitive load without actionable difference. Binary is instant: green = good, red = act.

**Implementation**: `_burn_rate_color()` simplifies to: `usage_pct < time_pct` → green, else → red. The `burn_medium` color key stays in constants (no breaking change) but is unused by this code path. The no-time fallback (usage only, no time data) uses `< 80%` → green, else → red.

### 3. Time stripe color: light gray
**Rationale**: Time elapsed is secondary context. Blue competes visually with the usage stripe. Light gray (`#d1d5db` in light theme, `#4b5563` in dark) recedes into the background.

**Implementation**: Change `bar_time` in all color profiles in `constants.py`.

### 4. Usage worker logging
**Rationale**: The log currently shows zero usage worker entries. When it freezes (e.g., curl-cffi blocking), there's no way to know.

**Implementation**: Add `logger.debug()` at: loop iteration start, API fetch attempt/result, local fallback attempt/result, sleep start. Matches existing pattern from feature_worker.

## Risks / Trade-offs

- [Amber removal] Users who relied on the amber "borderline" signal lose granularity → Acceptable trade-off per user request; the binary signal is more actionable
- [Log volume] Usage worker logs every 30s → Low volume (2 lines/30s), well within rotating log capacity (5MB)
- [Color profile consistency] `burn_medium` becomes unused → Keep the key in constants to avoid breaking any external themes; just stop referencing it
