## ADDED Requirements

### Requirement: Dual stripe rendering
The DualStripeBar widget renders two horizontal stripes (time elapsed on top, usage consumed on bottom) in a single 10px-tall widget using QPainter.

#### Scenario: Normal rendering with data
- **WHEN** `set_values(time_pct, usage_pct)` is called with valid percentages (0-100)
- **THEN** the top stripe fills left-to-right to `time_pct`% in the configured time color
- **AND** the bottom stripe fills left-to-right to `usage_pct`% in the configured usage color
- **AND** unfilled areas show the background color
- **AND** a 1px border surrounds the entire widget

#### Scenario: Empty state
- **WHEN** `set_empty()` is called
- **THEN** both stripes show only the background color with border (no fill)

#### Scenario: Clamping
- **WHEN** percentages exceed 0-100 range
- **THEN** values are clamped to 0-100 before rendering

### Requirement: Color configuration
Colors are set externally by the main window, not hardcoded in the widget.

#### Scenario: Color update
- **WHEN** `set_colors(time_color, usage_color, bg_color, border_color)` is called
- **THEN** the next `paintEvent` uses these colors for rendering

### Requirement: Combined label format
Each usage group shows a single label combining time remaining and usage percentage.

#### Scenario: API data available
- **WHEN** usage data is available from the API with time remaining and usage percentage
- **THEN** the label shows `"{time_remaining} · {usage_pct}%"` (e.g., "3h 12m · 42%")

#### Scenario: No data available
- **WHEN** usage data is not available
- **THEN** the 5h label shows `"-- · --/5h"` and the 7d label shows `"-- · --/7d"`

#### Scenario: Estimated data only
- **WHEN** only local estimated data is available (no API key)
- **THEN** labels show `"-- · --/5h"` and `"-- · --/7d"` with token count in tooltip
