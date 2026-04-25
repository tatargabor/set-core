"""Parity test between `config.DIRECTIVE_DEFAULTS` and `engine.Directives`.

Background: prior to verify-gate-resilience-fixes, `Directives` (engine.py) had
inline literal defaults that diverged from `DIRECTIVE_DEFAULTS` (config.py).
At runtime `parse_directives()` reads from raw input or falls back to the
class default — config.py wins when a key is in raw input, but the dataclass
default wins when constructed without parse. The divergence caused
craftbrew-run-20260423-2223 catalog-product-detail to spuriously hit
`failed:retry_wall_time_exhausted` after the 30→90 min code-default raise:
config.py kept 30 min and won at runtime, so the engine.py raise was a no-op.

This test asserts every field in `Directives` whose name matches a key in
`DIRECTIVE_DEFAULTS` has a default that EQUALS the canonical config value.
A failure means a future raise of one constant silently downgrades because
another source still holds the smaller value.
"""

from dataclasses import fields

from set_orch.config import DIRECTIVE_DEFAULTS
from set_orch.engine import Directives


# Fields in Directives that are HOISTED to DIRECTIVE_DEFAULTS and must match
# byte-for-byte at construction time.
HOISTED_FIELDS = {
    "max_verify_retries",
    "e2e_retry_limit",
    "max_stuck_loops",
    "per_change_token_runaway_threshold",
    "max_retry_wall_time_ms",
    "max_merge_retries",
    "max_integration_retries",
    "watchdog_timeout_running",
    "watchdog_timeout_verifying",
    "watchdog_timeout_dispatched",
    "issue_diagnosed_timeout_secs",
    "max_replan_retries",
}


def test_hoisted_fields_match_directive_defaults():
    """Every hoisted Directives field reads its default from DIRECTIVE_DEFAULTS."""
    d = Directives()
    divergences = []
    for name in HOISTED_FIELDS:
        if name not in DIRECTIVE_DEFAULTS:
            divergences.append(
                f"{name}: hoisted but missing from DIRECTIVE_DEFAULTS",
            )
            continue
        engine_val = getattr(d, name, None)
        config_val = DIRECTIVE_DEFAULTS[name]
        if engine_val != config_val:
            divergences.append(
                f"{name}: Directives default = {engine_val!r} but "
                f"DIRECTIVE_DEFAULTS[{name!r}] = {config_val!r}"
            )
    assert not divergences, (
        "Config↔Engine divergence detected. Either update DIRECTIVE_DEFAULTS "
        "or update Directives field default to use field(default_factory=...). "
        "Divergences: " + "; ".join(divergences)
    )


def test_hoisted_fields_present_in_directives():
    """Every key in HOISTED_FIELDS exists as an attribute on Directives."""
    d = Directives()
    field_names = {f.name for f in fields(d)}
    missing = [name for name in HOISTED_FIELDS if name not in field_names]
    assert not missing, (
        f"Hoisted fields not declared in Directives: {missing}"
    )


def test_directive_defaults_has_all_hoisted_keys():
    """Every key in HOISTED_FIELDS exists in DIRECTIVE_DEFAULTS."""
    missing = [name for name in HOISTED_FIELDS if name not in DIRECTIVE_DEFAULTS]
    assert not missing, (
        f"Hoisted keys missing from DIRECTIVE_DEFAULTS: {missing}. "
        f"Add them to lib/set_orch/config.py."
    )
