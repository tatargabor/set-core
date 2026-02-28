## Context

The Control Center shows API usage via dual progress bars (time elapsed + usage consumed) for both 5h and 7d windows. The current implementation uses two rows of QLabel-based gradient bars per group, taking ~43px of vertical space. This is excessive for a compact status window.

Current layout per group:
```
  --:-- left  [░░░░░░░░░░░]   ← row 1: time bar (18px)
  42%         [█████░░░░░░]   ← row 2: usage bar (18px)
                               + margins (~7px)
                               = ~43px total
```

## Goals / Non-Goals

**Goals:**
- Reduce usage area height from ~43px to ~22px
- Keep both time and usage info visible at a glance
- Maintain burn-rate-relative coloring for usage bar
- Keep detailed info in tooltips

**Non-Goals:**
- Changing the usage data fetching or worker
- Changing the color scheme or burn-rate logic
- Adding new usage metrics

## Decisions

### D1: Custom QPainter widget for dual stripes

Create `DualStripeBar(QWidget)` with `setFixedHeight(10)`. In `paintEvent`, draw two 5px horizontal stripes:
- Top stripe: time elapsed (neutral color `bar_time`)
- Bottom stripe: usage consumed (burn-rate color: `burn_low`/`burn_medium`/`burn_high`)

Each stripe fills left-to-right proportional to its percentage. Background is `bar_background` with 1px `bar_border` around the whole widget.

```
┌══════════════════════════════════┐
│▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░│ 5px — time (slate)
│█████████░░░░░░░░░░░░░░░░░░░░░░░│ 5px — usage (green/yellow/red)
└══════════════════════════════════┘
  10px total height
```

**Why QPainter over QLabel stylesheet gradients:** The current approach uses `qlineargradient` in stylesheet strings to simulate fill. This is fragile, requires recalculating stop values, and cannot draw two distinct stripes in one widget. QPainter gives pixel-level control with simpler code.

### D2: Combined label format

Merge time remaining + usage % into one label: `"{time} · {usage}%"`.

Examples:
- `3h 12m · 42%` (normal)
- `5d 2h · 15%` (weekly)
- `-- · --/5h` (no data)
- `-- · --/7d` (estimated mode)

Label width increases from 62px to 90px to fit the combined text.

### D3: Single-row layout per group

Each group becomes one `QHBoxLayout`:
```
[combined_label (90px)] [DualStripeBar (stretch)]
```

Two groups side by side in the outer `QHBoxLayout` with 15px spacing (unchanged).

### D4: API surface of DualStripeBar

```python
class DualStripeBar(QWidget):
    def __init__(self, parent=None):
        # setFixedHeight(10)

    def set_values(self, time_pct: float, usage_pct: float):
        # Store values, trigger repaint

    def set_colors(self, time_color: str, usage_color: str,
                   bg_color: str, border_color: str):
        # Store colors for paintEvent

    def set_empty(self, bg_color: str, border_color: str):
        # Reset to empty state

    def paintEvent(self, event):
        # Draw border, bg, top stripe (time), bottom stripe (usage)
```

The main window calls `set_colors()` then `set_values()` on each update. Color logic stays in `main_window.py` (burn-rate calculation unchanged).

### D5: Height constant update

With the compact bar, the usage area shrinks from ~43px to ~22px (one 18px label row + 2px margin + 10px bar = ~22px, vs two 18px rows + 7px margin = 43px). The `other_height` constant in `adjust_height_to_content` drops from 145 back to ~125.

## Alternatives Considered

**Stacked QProgressBar pair**: Qt's QProgressBar supports styling but not two fills in one widget without subclassing. Would still need two widgets stacked, losing the compactness goal.

**Single bar with split color**: One stripe alternating time/usage side by side. Rejected because it's confusing — the two metrics are independent percentages, not parts of a whole.
