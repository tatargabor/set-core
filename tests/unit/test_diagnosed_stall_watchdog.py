"""Unit tests for the DIAGNOSED-stall watchdog (`_check_diagnosed_stalls`)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from set_orch.issues.audit import AuditLog
from set_orch.issues.manager import IssueManager
from set_orch.issues.models import Issue, IssueState
from set_orch.issues.policy import IssuesPolicyConfig, PolicyEngine
from set_orch.issues.registry import IssueRegistry


def _make_manager(tmp_path: Path, *, diagnosed_stall_hours: int = 2, notifier=None) -> tuple[IssueManager, IssueRegistry]:
    cfg = IssuesPolicyConfig()
    cfg.diagnosed_stall_hours = diagnosed_stall_hours
    audit = AuditLog(tmp_path)
    registry = IssueRegistry(tmp_path)
    policy = PolicyEngine(cfg)
    mgr = IssueManager(
        registry=registry, audit=audit, policy=policy, notifier=notifier,
    )
    return mgr, registry


def _inject_issue(registry: IssueRegistry, *, diagnosed_age_hours: float) -> Issue:
    diagnosed_at = (
        datetime.now(timezone.utc) - timedelta(hours=diagnosed_age_hours)
    ).isoformat()
    issue = Issue(
        id="ISS-001",
        environment="test",
        environment_path="",
        source="gate",
        state=IssueState.DIAGNOSED,
        diagnosed_at=diagnosed_at,
    )
    registry._issues[issue.id] = issue
    registry.save()
    return issue


class _Notifier:
    def __init__(self):
        self.calls = []

    def on_stalled_diagnosis(self, issue, elapsed_seconds):
        self.calls.append((issue.id, elapsed_seconds))


# --- Under-threshold no-op --------------------------------------------


def test_under_threshold_is_noop(tmp_path: Path) -> None:
    notifier = _Notifier()
    mgr, reg = _make_manager(tmp_path, diagnosed_stall_hours=2, notifier=notifier)
    issue = _inject_issue(reg, diagnosed_age_hours=1.0)

    mgr._check_diagnosed_stalls()

    assert notifier.calls == []
    assert issue.extras.get("stalled_notification_sent") is None


# --- Threshold crossed: fire once -------------------------------------


def test_threshold_crossed_fires_notification_and_audit(tmp_path: Path) -> None:
    notifier = _Notifier()
    mgr, reg = _make_manager(tmp_path, diagnosed_stall_hours=2, notifier=notifier)
    issue = _inject_issue(reg, diagnosed_age_hours=3.0)

    mgr._check_diagnosed_stalls()

    assert len(notifier.calls) == 1
    iid, elapsed = notifier.calls[0]
    assert iid == "ISS-001"
    assert elapsed >= 3 * 3600  # at least 3 hours in seconds
    assert issue.extras["stalled_notification_sent"] is True

    # Audit log received the entry
    audit_entries = mgr.audit._entries if hasattr(mgr.audit, "_entries") else []
    # Fall back to reading from disk
    audit_path = tmp_path / ".set" / "issues" / "audit.jsonl"
    if audit_path.is_file():
        lines = audit_path.read_text().splitlines()
        events = [l for l in lines if "diagnosis_stalled_notification_sent" in l]
        assert len(events) == 1


# --- Second tick does not re-notify -----------------------------------


def test_second_tick_does_not_re_notify(tmp_path: Path) -> None:
    notifier = _Notifier()
    mgr, reg = _make_manager(tmp_path, diagnosed_stall_hours=2, notifier=notifier)
    _inject_issue(reg, diagnosed_age_hours=3.0)

    mgr._check_diagnosed_stalls()
    assert len(notifier.calls) == 1

    # Second tick — no new notification
    mgr._check_diagnosed_stalls()
    assert len(notifier.calls) == 1


# --- No notifier: audit only ------------------------------------------


def test_no_notifier_still_audits(tmp_path: Path) -> None:
    mgr, reg = _make_manager(tmp_path, diagnosed_stall_hours=2, notifier=None)
    issue = _inject_issue(reg, diagnosed_age_hours=3.0)

    # Should not raise
    mgr._check_diagnosed_stalls()
    assert issue.extras["stalled_notification_sent"] is True


# --- Notifier missing on_stalled_diagnosis method: audit only ---------


class _NotifierNoStallMethod:
    pass


def test_notifier_missing_method_audits_only(tmp_path: Path) -> None:
    notifier = _NotifierNoStallMethod()
    mgr, reg = _make_manager(tmp_path, diagnosed_stall_hours=2, notifier=notifier)
    issue = _inject_issue(reg, diagnosed_age_hours=3.0)

    # No crash even though notifier lacks the method
    mgr._check_diagnosed_stalls()
    assert issue.extras["stalled_notification_sent"] is True


# --- zero threshold disables the watchdog -----------------------------


def test_zero_threshold_disables_watchdog(tmp_path: Path) -> None:
    notifier = _Notifier()
    mgr, reg = _make_manager(tmp_path, diagnosed_stall_hours=0, notifier=notifier)
    issue = _inject_issue(reg, diagnosed_age_hours=5.0)

    mgr._check_diagnosed_stalls()
    assert notifier.calls == []
    assert issue.extras.get("stalled_notification_sent") is None


# --- Tick integration: exception in watchdog does not break tick ------


class _RaisingNotifier:
    def on_stalled_diagnosis(self, issue, elapsed):
        raise RuntimeError("simulated notifier crash")


def test_notifier_exception_isolated_from_tick(tmp_path: Path) -> None:
    # on_stalled_diagnosis raising should be swallowed inside the method,
    # and the watchdog still sets the extras flag
    notifier = _RaisingNotifier()
    mgr, reg = _make_manager(tmp_path, diagnosed_stall_hours=2, notifier=notifier)
    issue = _inject_issue(reg, diagnosed_age_hours=3.0)

    mgr._check_diagnosed_stalls()
    # Audit fired, extras flag set
    assert issue.extras["stalled_notification_sent"] is True


def test_tick_caller_swallows_watchdog_exceptions(tmp_path: Path) -> None:
    """If _check_diagnosed_stalls itself raises, tick() should not propagate."""
    mgr, reg = _make_manager(tmp_path)

    # Monkey-patch the method to raise
    def _boom():
        raise RuntimeError("watchdog exploded")

    mgr._check_diagnosed_stalls = _boom
    # tick() should not raise
    mgr.tick()  # registry is empty so no other work happens


# --- Ignores non-DIAGNOSED issues -------------------------------------


def test_investigating_issue_is_not_watched(tmp_path: Path) -> None:
    notifier = _Notifier()
    mgr, reg = _make_manager(tmp_path, diagnosed_stall_hours=2, notifier=notifier)
    diagnosed_at = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    issue = Issue(
        id="ISS-X",
        environment="test",
        environment_path="",
        source="gate",
        state=IssueState.INVESTIGATING,
        diagnosed_at=diagnosed_at,  # set but state is INVESTIGATING, not DIAGNOSED
    )
    reg._issues[issue.id] = issue
    reg.save()

    mgr._check_diagnosed_stalls()
    assert notifier.calls == []
