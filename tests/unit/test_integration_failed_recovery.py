"""Tests for integration-failed auto-recovery + in-flight exclusion.

Craftbrew-run-20260423-2223 deadlocked: catalog-product-detail went to
integration-failed after 3 merger retries, counted as 1 in-flight at
max_parallel=1, blocking all 18 remaining pending changes. The fix is
two-part:
  1. Exclude integration-failed from _NOT_IN_FLIGHT_STATUSES so it
     doesn't hold a parallel slot.
  2. Auto-recover integration-failed back to pending after cooldown,
     bounded by _INTEGRATION_FAILED_MAX_AUTO_RETRY attempts.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from set_orch import engine
from set_orch.state import (
    Change,
    OrchestratorState,
    count_in_flight_changes,
    load_state,
    save_state,
)


def _state_with(tmp_path: Path, extras: dict, status: str = "integration-failed") -> str:
    st = OrchestratorState(
        changes=[
            Change(
                name="foo", status=status,
                depends_on=[], roadmap_item="", scope="",
                extras=extras,
            ),
        ],
    )
    sp = str(tmp_path / "state.json")
    save_state(st, sp)
    return sp


def _field(ch, name, default=None):
    v = getattr(ch, name, None)
    if v is not None:
        return v
    return ch.extras.get(name, default)


# --- Part 1: in-flight exclusion -----------------------------------------


def test_integration_failed_not_counted_in_flight(tmp_path: Path) -> None:
    sp = _state_with(tmp_path, extras={})
    st = load_state(sp)
    assert count_in_flight_changes(st) == 0


def test_integration_e2e_failed_still_in_flight(tmp_path: Path) -> None:
    """integration-e2e-failed HAS auto-recovery — must stay in-flight."""
    sp = _state_with(tmp_path, extras={}, status="integration-e2e-failed")
    st = load_state(sp)
    assert count_in_flight_changes(st) == 1


def test_running_counted_in_flight(tmp_path: Path) -> None:
    sp = _state_with(tmp_path, extras={}, status="running")
    st = load_state(sp)
    assert count_in_flight_changes(st) == 1


# --- Part 2: auto-recovery path -------------------------------------------


def test_first_sighting_stamps_timestamp(tmp_path: Path) -> None:
    """On first observation, just record the timestamp — no flip yet."""
    sp = _state_with(tmp_path, extras={})
    engine._recover_integration_failed_safe(sp, SimpleNamespace(), None)
    ch = load_state(sp).changes[0]
    assert ch.status == "integration-failed"  # still failed
    assert _field(ch, "integration_failed_at") is not None
    assert int(_field(ch, "integration_failed_at") or 0) > 0


def test_before_cooldown_does_not_recover(tmp_path: Path) -> None:
    """If cooldown hasn't elapsed, leave the change alone."""
    now = int(time.time())
    sp = _state_with(tmp_path, extras={"integration_failed_at": now - 10})
    engine._recover_integration_failed_safe(sp, SimpleNamespace(), None)
    ch = load_state(sp).changes[0]
    assert ch.status == "integration-failed"


def test_after_cooldown_resets_to_pending(tmp_path: Path) -> None:
    """After cooldown, flip to pending + bump auto_retry counter."""
    old = int(time.time()) - engine._INTEGRATION_FAILED_COOLDOWN_SECONDS - 5
    sp = _state_with(tmp_path, extras={
        "integration_failed_at": old,
        "integration_e2e_retry_count": 3,  # budget exhausted
        "integration_auto_retry_count": 0,
        "retry_context": "sibling test foo failed",  # kept
    })
    engine._recover_integration_failed_safe(sp, SimpleNamespace(), None)
    ch = load_state(sp).changes[0]
    assert ch.status == "pending"
    assert _field(ch, "integration_e2e_retry_count") == 0  # reset
    assert _field(ch, "integration_auto_retry_count") == 1  # bumped
    assert _field(ch, "integration_failed_at") is None
    # retry_context preserved so agent sees prior failure context
    assert _field(ch, "retry_context") == "sibling test foo failed"


def test_cap_reached_stays_terminal(tmp_path: Path) -> None:
    """After MAX_AUTO_RETRY attempts, leave the change terminal forever."""
    old = int(time.time()) - engine._INTEGRATION_FAILED_COOLDOWN_SECONDS - 5
    sp = _state_with(tmp_path, extras={
        "integration_failed_at": old,
        "integration_auto_retry_count": engine._INTEGRATION_FAILED_MAX_AUTO_RETRY,
    })
    engine._recover_integration_failed_safe(sp, SimpleNamespace(), None)
    ch = load_state(sp).changes[0]
    assert ch.status == "integration-failed"
    # counter untouched (no bump past the cap)
    assert _field(ch, "integration_auto_retry_count") == engine._INTEGRATION_FAILED_MAX_AUTO_RETRY


def test_other_status_untouched(tmp_path: Path) -> None:
    """Must not touch changes in other statuses."""
    sp = _state_with(tmp_path, extras={}, status="pending")
    engine._recover_integration_failed_safe(sp, SimpleNamespace(), None)
    ch = load_state(sp).changes[0]
    assert ch.status == "pending"
    assert _field(ch, "integration_failed_at") is None


def test_max_auto_retry_value_is_generous(tmp_path: Path) -> None:
    """Regression guard: cap must stay >= 5 (sibling-test pollution needs rounds)."""
    assert engine._INTEGRATION_FAILED_MAX_AUTO_RETRY >= 5


def test_default_e2e_retry_limit_raised(tmp_path: Path) -> None:
    """Regression guard: merger e2e retry limit raised from 3 → 5+."""
    assert engine.DEFAULT_E2E_RETRY_LIMIT >= 5
