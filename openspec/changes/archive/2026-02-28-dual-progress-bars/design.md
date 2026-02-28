## Context

The Control Center GUI shows two usage progress bars (5h session, 7d weekly) at the top of the window. Each is a `QLabel` styled with a `qlineargradient` to simulate a filled bar (8px height). A text label to the left shows `"45% | 2h 30m"`. The usage data comes from `UsageWorker` which returns `session_pct`, `weekly_pct`, `session_reset`, and `weekly_reset`.

Currently the user sees quota consumption but has no visual reference for how much time has passed in the window. The burn rate is invisible.

## Goals / Non-Goals

**Goals:**
- Add a time-elapsed bar above each usage bar, creating a paired dual-bar for both 5h and 7d
- Show time% and usage% so the user can visually compare burn rate
- Keep the layout compact (the two dual-bar groups remain side-by-side)

**Non-Goals:**
- Changing the Ctx% column in the table (stays as-is, per-agent)
- Adding new data sources — time% is derived from existing reset timestamps
- Changing the usage worker or API layer

## Decisions

### D1: Layout — stacked bars with left-aligned labels

Each time window (5h, 7d) becomes a vertical stack of two rows:

```
label_time  ████████████░░░░░░  ← time-elapsed bar (top)
label_usage ████████░░░░░░░░░░  ← usage bar (bottom)
```

The two rows have **0px vertical spacing**. The two groups (5h and 7d) remain **side-by-side** with a 15px horizontal gap (same as current).

Implementation: Replace the single `QHBoxLayout` usage_row with a nested layout:

```
usage_row (QHBoxLayout)
├── 5h_group (QVBoxLayout, spacing=0)
│   ├── 5h_time_row (QHBoxLayout)
│   │   ├── usage_5h_time_label (QLabel, fixed width)
│   │   └── usage_5h_time_bar (QLabel, stretch=1, height=6)
│   └── 5h_usage_row (QHBoxLayout)
│       ├── usage_5h_label (QLabel, fixed width)
│       └── usage_5h_bar (QLabel, stretch=1, height=6)
├── spacer (15px)
└── 7d_group (QVBoxLayout, spacing=0)
    ├── 7d_time_row (QHBoxLayout)
    │   ├── usage_7d_time_label (QLabel, fixed width)
    │   └── usage_7d_time_bar (QLabel, stretch=1, height=6)
    └── 7d_usage_row (QHBoxLayout)
        ├── usage_7d_label (QLabel, fixed width)
        └── usage_7d_bar (QLabel, stretch=1, height=6)
```

Bar height reduced from 8px to 6px so the total (12px) stays close to the original 8px.

**Rationale:** Keeping the groups side-by-side avoids doubling vertical space. Reducing bar height to 6px keeps the pair compact.

### D2: Time-elapsed percentage calculation

```python
def calc_time_elapsed_pct(reset_time_str, window_hours):
    """How far through the window are we? 0% = just reset, 100% = about to reset."""
    reset = parse(reset_time_str)
    now = datetime.now(timezone.utc)
    window = timedelta(hours=window_hours)
    window_start = reset - window
    elapsed = (now - window_start).total_seconds()
    return clamp(elapsed / window.total_seconds() * 100, 0, 100)
```

For 5h: `window_hours=5`. For 7d: `window_hours=168`.

**Rationale:** `session_reset` is the future reset timestamp. Subtracting the window size gives us when it started. The ratio of elapsed to total gives the time percentage.

### D3: Label format

- **Time label**: `"60%, 2h"` — time-elapsed percentage, then remaining time (comma-separated)
- **Usage label**: `"42%"` — just the usage percentage

Labels use a fixed width so the bars align vertically.

When no API data: time label shows `"--"`, usage label shows `"--/5h"` or `"--/7d"` (same as current).

### D4: Color logic — burn-rate-relative

The **time bar** is always a neutral color (the theme's `bar_time` — a muted blue/gray).

The **usage bar** color is based on comparison with time:
- `usage_pct < time_pct - 5` → green (under pace, healthy)
- `time_pct - 5 <= usage_pct <= time_pct + 5` → yellow (on pace)
- `usage_pct > time_pct + 5` → red (over pace, burning fast)

The 5% deadband avoids flickering between colors when the values are close.

**Rationale:** This replaces the current absolute thresholds (90%/110%) with a relative comparison that's more useful. When you're 80% through the time window, 80% usage is fine (yellow, on pace) — the old logic would show red.

### D5: New theme color

Add `bar_time` to `constants.py` color profiles:
- Light: `#94a3b8` (slate-400)
- Dark: `#64748b` (slate-500)
- Gray: `#6b7280` (gray-500)
- High contrast: `#9ca3af` (gray-400)

## Risks / Trade-offs

- **[Layout height increase]** Total bar area goes from 8px to ~12px. Minimal impact on the compact UI. → Mitigation: 6px bar height instead of 8px.
- **[No API data = no time bar]** Without `session_reset`/`weekly_reset`, time% can't be computed. → Mitigation: show empty bars and `"--"` label, same as current fallback behavior.
- **[Label width]** Fixed-width labels may clip on very high percentages with long time strings. → Mitigation: use `"100%, 0m"` as the longest expected string and size accordingly.
