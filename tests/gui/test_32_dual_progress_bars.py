"""
Compact Dual-Stripe Bar Tests - Verify DualStripeBar widget and combined labels
"""

from datetime import datetime, timezone, timedelta

from gui.widgets import DualStripeBar


def test_dual_stripe_bars_exist(control_center):
    """Both DualStripeBar widgets should exist."""
    assert hasattr(control_center, 'usage_5h_bar')
    assert hasattr(control_center, 'usage_7d_bar')
    assert isinstance(control_center.usage_5h_bar, DualStripeBar)
    assert isinstance(control_center.usage_7d_bar, DualStripeBar)


def test_combined_labels_exist(control_center):
    """Both combined labels should exist."""
    assert hasattr(control_center, 'usage_5h_label')
    assert hasattr(control_center, 'usage_7d_label')


def test_bar_height_is_10px(control_center):
    """DualStripeBar should be 10px height."""
    assert control_center.usage_5h_bar.maximumHeight() == 10
    assert control_center.usage_7d_bar.maximumHeight() == 10


def test_time_elapsed_pct_midpoint(control_center):
    """calc_time_elapsed_pct should return ~50% when halfway through window."""
    now = datetime.now(timezone.utc)
    # Reset is 2.5h from now in a 5h window -> 50% elapsed
    reset = (now + timedelta(hours=2.5)).isoformat()
    pct = control_center.calc_time_elapsed_pct(reset, 5)
    assert 45 <= pct <= 55, f"Expected ~50%, got {pct}"


def test_time_elapsed_pct_near_start(control_center):
    """calc_time_elapsed_pct should return ~0% right after reset."""
    now = datetime.now(timezone.utc)
    # Reset is almost 5h away -> just started
    reset = (now + timedelta(hours=4, minutes=59)).isoformat()
    pct = control_center.calc_time_elapsed_pct(reset, 5)
    assert pct < 5, f"Expected ~0%, got {pct}"


def test_time_elapsed_pct_near_end(control_center):
    """calc_time_elapsed_pct should return ~100% just before reset."""
    now = datetime.now(timezone.utc)
    # Reset is 1 minute away -> almost done
    reset = (now + timedelta(minutes=1)).isoformat()
    pct = control_center.calc_time_elapsed_pct(reset, 5)
    assert pct > 95, f"Expected ~100%, got {pct}"


def test_time_elapsed_pct_clamped(control_center):
    """calc_time_elapsed_pct should clamp to 0-100."""
    # Past reset -> should clamp to 100
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert control_center.calc_time_elapsed_pct(past, 5) == 100

    # None -> should return 0
    assert control_center.calc_time_elapsed_pct(None, 5) == 0


def test_burn_rate_color_under_pace(control_center):
    """_burn_rate_color should return green when usage < time - 5."""
    color = control_center._burn_rate_color(30, 60)
    assert color == control_center.get_color("burn_low")


def test_burn_rate_color_on_pace(control_center):
    """_burn_rate_color should return yellow when usage ~ time."""
    color = control_center._burn_rate_color(58, 60)
    assert color == control_center.get_color("burn_medium")


def test_burn_rate_color_over_pace(control_center):
    """_burn_rate_color should return red when usage > time + 5."""
    color = control_center._burn_rate_color(80, 60)
    assert color == control_center.get_color("burn_high")


def test_fallback_no_api_data(control_center):
    """When no API data, combined labels show '-- \u00b7 --/5h' and '-- \u00b7 --/7d'."""
    control_center.update_usage({"available": False})
    assert control_center.usage_5h_label.text() == "-- \u00b7 --/5h"
    assert control_center.usage_7d_label.text() == "-- \u00b7 --/7d"


def test_fallback_estimated(control_center):
    """When estimated (no session key), combined labels show -- with tooltips."""
    control_center.update_usage({
        "available": True,
        "is_estimated": True,
        "session_tokens": 150000,
        "weekly_tokens": 1000000,
    })
    assert control_center.usage_5h_label.text() == "-- \u00b7 --/5h"
    assert "150k" in control_center.usage_5h_label.toolTip()
    assert "1000k" in control_center.usage_7d_label.toolTip()


def test_api_data_combined_label_format(control_center):
    """With API data, combined label shows '{time} \u00b7 {pct}%'."""
    now = datetime.now(timezone.utc)
    control_center.update_usage({
        "available": True,
        "session_pct": 42,
        "weekly_pct": 55,
        "session_reset": (now + timedelta(hours=2)).isoformat(),
        "weekly_reset": (now + timedelta(days=2)).isoformat(),
    })
    label_5h = control_center.usage_5h_label.text()
    label_7d = control_center.usage_7d_label.text()
    # Should contain middle dot separator and percentage
    assert "\u00b7" in label_5h, f"Expected middle dot in label, got: {label_5h}"
    assert "42%" in label_5h, f"Expected '42%' in label, got: {label_5h}"
    assert "55%" in label_7d, f"Expected '55%' in label, got: {label_7d}"


def test_dual_stripe_bar_set_values(control_center):
    """DualStripeBar.set_values clamps and stores percentages."""
    bar = control_center.usage_5h_bar
    bar.set_values(50, 75)
    assert bar._time_pct == 50
    assert bar._usage_pct == 75

    # Clamping
    bar.set_values(-10, 150)
    assert bar._time_pct == 0
    assert bar._usage_pct == 100


def test_bar_time_color_in_all_profiles(control_center):
    """bar_time color should exist in all theme profiles."""
    from gui.constants import COLOR_PROFILES
    for profile_name, profile in COLOR_PROFILES.items():
        assert "bar_time" in profile, f"bar_time missing from {profile_name} profile"
