## Why

The dual progress bar layout (time + usage) introduced a two-row structure per group that takes ~43px of vertical space. In a compact status window where every pixel matters, this is excessive for what is essentially two percentages. A custom paint widget can show both stripes in ~10px height with a single combined label, halving the vertical footprint.

## What Changes

- Replace the two-row layout (QLabel time bar + QLabel usage bar per group) with a single custom `DualStripeBar` widget that paints two horizontal stripes stacked vertically in `paintEvent`
- Merge the two separate labels (time remaining + usage %) into one combined label per group (e.g., "3h · 42%")
- Reduce usage area height from ~43px to ~22px (one label row + 10px bar + margins)
- Update `adjust_height_to_content()` to reflect the reduced chrome height
- Keep detailed info accessible via tooltips on both label and bar

## Capabilities

### New Capabilities
- `dual-stripe-bar`: Custom QWidget that renders two stacked horizontal progress stripes (time elapsed + usage) in a single compact bar using QPainter

### Modified Capabilities
- `usage-display`: Label format changes from two separate labels to one combined label; bar rendering moves from QLabel stylesheet gradients to QPainter-based custom widget

## Impact

- `gui/control_center/main_window.py` — setup_ui (bar creation), update_usage_bars, _fill_bar, update_usage_bar, adjust_height_to_content
- `gui/constants.py` — no changes needed (same color keys used)
- New file: `gui/widgets/dual_stripe_bar.py` — the custom widget
- `gui/control_center/mixins/handlers.py` — no changes (connects signal only)
