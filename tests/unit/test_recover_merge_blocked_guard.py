"""Tests for _recover_merge_blocked_safe last_recover_ts guard (F1).

The fix prevents the 29h toggle loop observed in craftbrew-run-20260421-0025
where a long-resolved issue kept re-triggering ff_retry_count reset on
every poll, bouncing a change between merge-blocked and done.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from set_orch import engine
from set_orch.state import Change, OrchestratorState, load_state, save_state


def _field(ch, name, default=None):
    """Read a counter from the dataclass attr if present, else extras."""
    v = getattr(ch, name, None)
    if v is not None:
        return v
    return ch.extras.get(name, default)


def _seed(tmp_path: Path, issues: list[dict], change_extras: dict) -> str:
    """Seed a state file + issue registry for the recovery test."""
    state = OrchestratorState(
        changes=[
            Change(
                name="foo", status="merge-blocked",
                depends_on=[], roadmap_item="", scope="",
                extras=change_extras,
            ),
        ],
    )
    sp = str(tmp_path / "state.json")
    save_state(state, sp)
    # Issue registry at CWD/.set/issues/registry.json (what the code reads)
    reg = tmp_path / ".set" / "issues"
    reg.mkdir(parents=True, exist_ok=True)
    (reg / "registry.json").write_text(json.dumps({"issues": issues}))
    return sp


@pytest.fixture(autouse=True)
def _chdir(tmp_path, monkeypatch):
    """_recover_merge_blocked_safe reads .set/issues/registry.json from CWD."""
    monkeypatch.chdir(tmp_path)


def test_first_resolution_triggers_recovery(tmp_path: Path) -> None:
    """Initial credit: no last_recover_ts yet, issue is resolved → reset + done."""
    sp = _seed(
        tmp_path,
        issues=[{
            "affected_change": "foo", "state": "resolved",
            "resolved_at": "2026-04-23T10:00:00Z",
        }],
        change_extras={"ff_retry_count": 3, "merge_retry_count": 0},
    )
    engine._recover_merge_blocked_safe(sp, MagicMock())
    ch = load_state(sp).changes[0]
    assert ch.status == "done"
    assert _field(ch, "ff_retry_count") == 0
    assert _field(ch, "merge_retry_count") == 1
    assert _field(ch, "last_recover_ts") == "2026-04-23T10:00:00Z"


def test_stale_resolution_does_not_re_trigger_recovery(tmp_path: Path) -> None:
    """The root cause of the 29h stall: resolution already credited, must not re-reset."""
    sp = _seed(
        tmp_path,
        issues=[{
            "affected_change": "foo", "state": "resolved",
            "resolved_at": "2026-04-23T10:00:00Z",
        }],
        change_extras={
            "ff_retry_count": 3, "merge_retry_count": 1,
            "last_recover_ts": "2026-04-23T10:00:00Z",  # already credited
        },
    )
    engine._recover_merge_blocked_safe(sp, MagicMock())
    ch = load_state(sp).changes[0]
    # Must stay merge-blocked, counters untouched
    assert ch.status == "merge-blocked"
    assert _field(ch, "ff_retry_count") == 3
    assert _field(ch, "merge_retry_count") == 1


def test_newer_resolution_after_credited_one_triggers_recovery(tmp_path: Path) -> None:
    """When a fresh issue resolves AFTER the last credited one, credit it too."""
    sp = _seed(
        tmp_path,
        issues=[
            {"affected_change": "foo", "state": "resolved",
             "resolved_at": "2026-04-23T10:00:00Z"},
            {"affected_change": "foo", "state": "resolved",
             "resolved_at": "2026-04-23T15:30:00Z"},  # newer
        ],
        change_extras={
            "ff_retry_count": 3,
            "last_recover_ts": "2026-04-23T10:00:00Z",
        },
    )
    engine._recover_merge_blocked_safe(sp, MagicMock())
    ch = load_state(sp).changes[0]
    assert ch.status == "done"
    assert _field(ch, "ff_retry_count") == 0
    # Credit was moved forward to the newer resolution
    assert _field(ch, "last_recover_ts") == "2026-04-23T15:30:00Z"


def test_no_issues_marks_integration_failed(tmp_path: Path) -> None:
    """When FF exhausted with no issues, mark integration-failed (existing behavior)."""
    sp = _seed(
        tmp_path, issues=[],
        change_extras={"ff_retry_count": 3},
    )
    engine._recover_merge_blocked_safe(sp, MagicMock())
    ch = load_state(sp).changes[0]
    assert ch.status == "integration-failed"


def test_active_issue_blocks_recovery(tmp_path: Path) -> None:
    """Active blocker (investigating/diagnosed/...) should NOT trigger recovery."""
    sp = _seed(
        tmp_path,
        issues=[{
            "affected_change": "foo", "state": "investigating",
            "resolved_at": None, "updated_at": "2026-04-23T10:00:00Z",
        }],
        change_extras={"ff_retry_count": 3},
    )
    engine._recover_merge_blocked_safe(sp, MagicMock())
    ch = load_state(sp).changes[0]
    # Still merge-blocked — active issue blocks recovery
    assert ch.status == "merge-blocked"
    assert _field(ch, "ff_retry_count") == 3


def test_cancelled_issue_with_updated_at_fallback(tmp_path: Path) -> None:
    """Cancelled/dismissed issues have no resolved_at — fall back to updated_at."""
    sp = _seed(
        tmp_path,
        issues=[{
            "affected_change": "foo", "state": "cancelled",
            "resolved_at": None,
            "updated_at": "2026-04-23T12:00:00Z",
        }],
        change_extras={"ff_retry_count": 3},
    )
    engine._recover_merge_blocked_safe(sp, MagicMock())
    ch = load_state(sp).changes[0]
    assert ch.status == "done"
    assert _field(ch, "last_recover_ts") == "2026-04-23T12:00:00Z"


def test_unrelated_change_issues_ignored(tmp_path: Path) -> None:
    """Issues for OTHER changes must not affect this one's recovery."""
    sp = _seed(
        tmp_path,
        issues=[{
            "affected_change": "bar",  # different change
            "state": "resolved",
            "resolved_at": "2026-04-23T10:00:00Z",
        }],
        change_extras={"ff_retry_count": 3},
    )
    engine._recover_merge_blocked_safe(sp, MagicMock())
    ch = load_state(sp).changes[0]
    # No issues for `foo` → integration-failed (empty path)
    assert ch.status == "integration-failed"
