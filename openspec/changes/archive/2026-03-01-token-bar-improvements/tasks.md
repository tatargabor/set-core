## 1. DualStripeBar Widget — Swap Stripe Order

- [x] 1.1 In `gui/widgets/dual_stripe_bar.py` `paintEvent()`: swap the two `fillRect` calls so usage stripe renders on top (y=1) and time stripe renders on bottom (y=1+stripe_h)

## 2. Color Constants — bar_time to Gray

- [x] 2.1 In `gui/constants.py`: change `bar_time` value in all color profiles — light: `#d1d5db`, dark: `#4b5563`, gray: `#6b7280`, high_contrast: `#888888`

## 3. Burn Rate Color — Binary Green/Red

- [x] 3.1 In `gui/control_center/main_window.py` `_burn_rate_color()`: simplify to binary logic — `usage_pct < time_pct` returns `burn_low` (green), else returns `burn_high` (red). No-time fallback: `< 80%` green, else red

## 4. Status Bar Rendering — Argument Order

- [x] 4.1 In `gui/control_center/main_window.py` `update_usage_bars()`: no change needed — widget `set_values(time_pct, usage_pct)` signature is unchanged, the `paintEvent` swap handles the visual reorder internally

## 5. Usage Worker Logging

- [x] 5.1 In `gui/workers/usage.py` `run()`: add `logger.debug` at poll cycle start with account count
- [x] 5.2 In `gui/workers/usage.py` `run()`: add `logger.debug` after each account API fetch with result (success/source or failure)
- [x] 5.3 In `gui/workers/usage.py` `run()`: add `logger.warning` when API fetch fails for an account (all fallbacks exhausted)
- [x] 5.4 In `gui/workers/usage.py` `run()`: add `logger.debug` before sleep with next poll time

## 6. Tests

- [x] 6.1 Add or update tests in `tests/gui/` for `_burn_rate_color()` binary logic (green below, red at/above time_pct, fallback without time data)
- [x] 6.2 Add or update tests in `tests/gui/` for `DualStripeBar` stripe order (verify usage stripe renders at top y-position)
