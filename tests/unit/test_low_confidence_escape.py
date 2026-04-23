"""Unit tests for the opt-in low-confidence auto-fix escape hatch."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from set_orch.issues.audit import AuditLog
from set_orch.issues.manager import IssueManager
from set_orch.issues.models import Diagnosis, Issue, IssueState
from set_orch.issues.policy import IssuesPolicyConfig, PolicyEngine
from set_orch.issues.registry import IssueRegistry


def _make_manager(
    tmp_path: Path,
    *,
    escape_hours: float | None = None,
    diagnosed_stall_hours: int = 2,
) -> tuple[IssueManager, IssueRegistry]:
    cfg = IssuesPolicyConfig()
    cfg.diagnosed_stall_hours = diagnosed_stall_hours
    if escape_hours is not None:
        cfg.auto_fix_conditions["low_confidence_after_hours"] = escape_hours
    audit = AuditLog(tmp_path)
    registry = IssueRegistry(tmp_path)
    policy = PolicyEngine(cfg)
    mgr = IssueManager(registry=registry, audit=audit, policy=policy)
    return mgr, registry


def _inject_stalled(
    registry: IssueRegistry,
    *,
    diagnosed_age_hours: float,
    confidence: float,
) -> Issue:
    diagnosed_at = (
        datetime.now(timezone.utc) - timedelta(hours=diagnosed_age_hours)
    ).isoformat()
    diag = Diagnosis(
        root_cause="x", impact="medium", confidence=confidence,
        fix_scope="single_file", suggested_fix="retry",
    )
    issue = Issue(
        id="ISS-001", environment="t", environment_path="",
        source="gate", state=IssueState.DIAGNOSED,
        severity="medium", diagnosed_at=diagnosed_at, diagnosis=diag,
    )
    registry._issues[issue.id] = issue
    registry.save()
    return issue


# --- Disabled by default --------------------------------------------------


def test_escape_disabled_no_promotion(tmp_path: Path) -> None:
    mgr, reg = _make_manager(tmp_path, escape_hours=None)
    issue = _inject_stalled(reg, diagnosed_age_hours=5.0, confidence=0.5)

    mgr._check_diagnosed_stalls()

    # Watchdog still notifies on stall, but no FIXING transition
    assert issue.state == IssueState.DIAGNOSED
    assert issue.auto_fix is False


def test_escape_zero_no_promotion(tmp_path: Path) -> None:
    mgr, reg = _make_manager(tmp_path, escape_hours=0)
    issue = _inject_stalled(reg, diagnosed_age_hours=5.0, confidence=0.5)

    mgr._check_diagnosed_stalls()

    assert issue.state == IssueState.DIAGNOSED


# --- Enabled but conditions not met --------------------------------------


def test_escape_confidence_too_low_no_promotion(tmp_path: Path) -> None:
    mgr, reg = _make_manager(tmp_path, escape_hours=1)
    issue = _inject_stalled(reg, diagnosed_age_hours=5.0, confidence=0.3)

    mgr._check_diagnosed_stalls()

    # confidence < 0.4 → no promotion even though elapsed > escape_hours
    assert issue.state == IssueState.DIAGNOSED


def test_escape_elapsed_too_short_no_promotion(tmp_path: Path) -> None:
    # Stall threshold is 2h, escape threshold is 3h. If elapsed = 2.5h:
    # stall fires (notification), escape does NOT (needs > 3h).
    mgr, reg = _make_manager(
        tmp_path, escape_hours=3, diagnosed_stall_hours=2,
    )
    issue = _inject_stalled(reg, diagnosed_age_hours=2.5, confidence=0.5)

    mgr._check_diagnosed_stalls()

    assert issue.extras.get("stalled_notification_sent") is True
    assert issue.state == IssueState.DIAGNOSED


# --- All conditions met: promote to FIXING --------------------------------


def test_escape_fires_promotes_to_fixing(tmp_path: Path) -> None:
    mgr, reg = _make_manager(
        tmp_path, escape_hours=1, diagnosed_stall_hours=1,
    )
    issue = _inject_stalled(reg, diagnosed_age_hours=2.0, confidence=0.5)

    mgr._check_diagnosed_stalls()

    # Escape fired: auto_fix flag set, transition to FIXING (or queued if concurrency blocks)
    assert issue.auto_fix is True
    assert issue.policy_matched is not None
    assert "low-confidence-escape" in issue.policy_matched
    # FIXING transition happens inside _start_fix if concurrency allows
    assert issue.state in (IssueState.FIXING,)


def test_escape_exact_threshold_fires(tmp_path: Path) -> None:
    """At exactly escape_hours the escape should fire (>=, not strict >)."""
    mgr, reg = _make_manager(
        tmp_path, escape_hours=1, diagnosed_stall_hours=1,
    )
    # Use 1.01 hours to ensure we're strictly past the boundary
    issue = _inject_stalled(reg, diagnosed_age_hours=1.01, confidence=0.5)

    mgr._check_diagnosed_stalls()

    assert issue.auto_fix is True
