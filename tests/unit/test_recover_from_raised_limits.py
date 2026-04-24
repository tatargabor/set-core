"""Tests for engine._recover_from_raised_limits — auto-recovery when the
operator bumps token-runaway / wall-time limits.

Built in response to craftbrew-run-20260423-2223 deadlock: catalog-product-detail
(failed:retry_wall_time_exhausted) and auth-user-registration-and-login
(failed:token_runaway) were stuck terminal even after the operator raised both
limits. The user wanted: "raise the limit, pull it out of deadlock, continue
where it left off". This is the framework-level mechanism that does it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import engine
from set_orch.state import (
    Change,
    OrchestratorState,
    load_state,
    save_state,
)


def _state_with(tmp_path: Path, change: Change) -> str:
    st = OrchestratorState(changes=[change])
    sp = str(tmp_path / "state.json")
    save_state(st, sp)
    return sp


def _field(ch, name, default=None):
    v = getattr(ch, name, None)
    if v is not None:
        return v
    return ch.extras.get(name, default)


# --- token_runaway recovery ----------------------------------------------


def test_token_runaway_recovers_when_limit_raised(tmp_path: Path) -> None:
    """failed:token_runaway with old_limit < new_limit → reset to pending."""
    sp = _state_with(tmp_path, Change(
        name="foo", status="failed:token_runaway",
        worktree_path="/tmp/wt-foo",
        retry_wall_time_ms=300_000,
        token_runaway_baseline=82_000_000,
        depends_on=[], roadmap_item="", scope="",
        extras={
            "token_runaway_threshold_at_failure": 20_000_000,
            "token_runaway_fingerprint": "sha256:abc",
            "fix_iss_child": "fix-iss-002-foo",
            "stall_reason": "token_runaway_old",
        },
    ))
    d = SimpleNamespace(
        per_change_token_runaway_threshold=50_000_000,  # raised from 20M
        max_retry_wall_time_ms=1_800_000,
    )

    n = engine._recover_from_raised_limits(sp, d, None)
    assert n == 1

    ch = load_state(sp).changes[0]
    assert ch.status == "pending"
    # Worktree + accumulated wall time preserved
    assert ch.worktree_path == "/tmp/wt-foo"
    assert int(ch.retry_wall_time_ms or 0) == 300_000
    # Breaker state cleared so the new threshold actually applies
    assert _field(ch, "token_runaway_baseline") in (None, 0)
    assert _field(ch, "token_runaway_fingerprint") in (None, "")
    # Fix-iss link detached
    assert _field(ch, "fix_iss_child") in (None, "")
    # Stall reason cleared
    assert _field(ch, "stall_reason") in (None, "")
    # Recovery counter bumped
    assert _field(ch, "limit_raised_auto_retry_count") == 1


def test_token_runaway_does_not_recover_when_limit_unchanged(tmp_path: Path) -> None:
    """If new_limit == old_limit, no recovery (would just re-trip)."""
    sp = _state_with(tmp_path, Change(
        name="foo", status="failed:token_runaway",
        depends_on=[], roadmap_item="", scope="",
        extras={"token_runaway_threshold_at_failure": 20_000_000},
    ))
    d = SimpleNamespace(
        per_change_token_runaway_threshold=20_000_000,  # NOT raised
        max_retry_wall_time_ms=1_800_000,
    )
    n = engine._recover_from_raised_limits(sp, d, None)
    assert n == 0
    assert load_state(sp).changes[0].status == "failed:token_runaway"


def test_token_runaway_does_not_recover_when_limit_lowered(tmp_path: Path) -> None:
    """Operator lowering the limit shouldn't trigger recovery (would re-trip)."""
    sp = _state_with(tmp_path, Change(
        name="foo", status="failed:token_runaway",
        depends_on=[], roadmap_item="", scope="",
        extras={"token_runaway_threshold_at_failure": 50_000_000},
    ))
    d = SimpleNamespace(
        per_change_token_runaway_threshold=20_000_000,  # LOWERED
        max_retry_wall_time_ms=1_800_000,
    )
    assert engine._recover_from_raised_limits(sp, d, None) == 0


def test_token_runaway_skips_when_no_snapshot(tmp_path: Path) -> None:
    """Legacy failed:token_runaway without snapshot → no auto-recover.

    We don't know what limit was active, so don't blind-recover.
    """
    sp = _state_with(tmp_path, Change(
        name="foo", status="failed:token_runaway",
        depends_on=[], roadmap_item="", scope="",
        extras={},  # no snapshot
    ))
    d = SimpleNamespace(
        per_change_token_runaway_threshold=50_000_000,
        max_retry_wall_time_ms=1_800_000,
    )
    assert engine._recover_from_raised_limits(sp, d, None) == 0


# --- wall_time recovery --------------------------------------------------


def test_wall_time_recovers_when_budget_raised(tmp_path: Path) -> None:
    """failed:retry_wall_time_exhausted with old_budget < new_budget → recover."""
    sp = _state_with(tmp_path, Change(
        name="foo", status="failed:retry_wall_time_exhausted",
        worktree_path="/tmp/wt-foo",
        retry_wall_time_ms=1_800_000,  # already burned the old 30 min cap
        depends_on=[], roadmap_item="", scope="",
        extras={
            "wall_time_budget_at_failure": 1_800_000,
            "fix_iss_child": "fix-iss-001-foo",
        },
    ))
    d = SimpleNamespace(
        per_change_token_runaway_threshold=20_000_000,
        max_retry_wall_time_ms=5_400_000,  # raised from 30 min → 90 min
    )
    n = engine._recover_from_raised_limits(sp, d, None)
    assert n == 1

    ch = load_state(sp).changes[0]
    assert ch.status == "pending"
    # Wall time IS preserved — agent picks up where it stopped.
    # New cap is 90 min, already spent 30 min → effective new budget = 60 min.
    assert int(ch.retry_wall_time_ms or 0) == 1_800_000
    assert ch.worktree_path == "/tmp/wt-foo"
    assert _field(ch, "fix_iss_child") in (None, "")
    assert _field(ch, "limit_raised_auto_retry_count") == 1


def test_wall_time_does_not_recover_when_budget_unchanged(tmp_path: Path) -> None:
    sp = _state_with(tmp_path, Change(
        name="foo", status="failed:retry_wall_time_exhausted",
        depends_on=[], roadmap_item="", scope="",
        extras={"wall_time_budget_at_failure": 1_800_000},
    ))
    d = SimpleNamespace(
        per_change_token_runaway_threshold=20_000_000,
        max_retry_wall_time_ms=1_800_000,  # not raised
    )
    assert engine._recover_from_raised_limits(sp, d, None) == 0


# --- cap enforcement -----------------------------------------------------


def test_recovery_cap_prevents_infinite_loop(tmp_path: Path) -> None:
    """After _LIMIT_RAISE_RECOVERY_MAX recoveries, leave terminal."""
    sp = _state_with(tmp_path, Change(
        name="foo", status="failed:token_runaway",
        depends_on=[], roadmap_item="", scope="",
        extras={
            "token_runaway_threshold_at_failure": 20_000_000,
            "limit_raised_auto_retry_count": engine._LIMIT_RAISE_RECOVERY_MAX,
        },
    ))
    d = SimpleNamespace(
        per_change_token_runaway_threshold=100_000_000,  # raised many times
        max_retry_wall_time_ms=1_800_000,
    )
    assert engine._recover_from_raised_limits(sp, d, None) == 0
    assert load_state(sp).changes[0].status == "failed:token_runaway"


def test_recovery_cap_value_is_reasonable(tmp_path: Path) -> None:
    """Regression guard: cap must stay >= 3 (give operator a few chances)."""
    assert engine._LIMIT_RAISE_RECOVERY_MAX >= 3


# --- non-applicable statuses --------------------------------------------


def test_skips_other_failed_statuses(tmp_path: Path) -> None:
    """failed:stuck_no_progress and failed:retry_budget_exhausted are NOT
    in scope — they're terminal for different reasons (genuine agent
    inability vs limit being too tight)."""
    for status in (
        "failed:stuck_no_progress",
        "failed:retry_budget_exhausted",
        "failed",
    ):
        sp = _state_with(tmp_path, Change(
            name=f"foo-{status}", status=status,
            depends_on=[], roadmap_item="", scope="",
            extras={"token_runaway_threshold_at_failure": 20_000_000},
        ))
        d = SimpleNamespace(
            per_change_token_runaway_threshold=50_000_000,
            max_retry_wall_time_ms=5_400_000,
        )
        assert engine._recover_from_raised_limits(sp, d, None) == 0, (
            f"Should not recover {status}"
        )


def test_skips_pending_changes(tmp_path: Path) -> None:
    """Non-failed statuses are no-ops."""
    sp = _state_with(tmp_path, Change(
        name="foo", status="pending",
        depends_on=[], roadmap_item="", scope="",
    ))
    d = SimpleNamespace(
        per_change_token_runaway_threshold=50_000_000,
        max_retry_wall_time_ms=5_400_000,
    )
    assert engine._recover_from_raised_limits(sp, d, None) == 0
