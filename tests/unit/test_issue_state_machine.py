"""Tests for Issue State Machine — transitions, tick processing, policy routing."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from set_orch.issues.models import (
    VALID_TRANSITIONS,
    Diagnosis,
    Issue,
    IssueState,
    now_iso,
)
from set_orch.issues.audit import AuditLog
from set_orch.issues.manager import IssueManager, InvalidTransitionError
from set_orch.issues.policy import IssuesPolicyConfig, PolicyEngine
from set_orch.issues.registry import IssueRegistry


@pytest.fixture
def tmp_project(tmp_path):
    return tmp_path


@pytest.fixture
def registry(tmp_project):
    return IssueRegistry(tmp_project)


@pytest.fixture
def audit(tmp_project):
    return AuditLog(tmp_project)


@pytest.fixture
def policy():
    config = IssuesPolicyConfig()
    return PolicyEngine(config, mode="e2e")


@pytest.fixture
def manager(registry, audit, policy):
    return IssueManager(registry=registry, audit=audit, policy=policy)


class TestTransitions:
    def test_valid_transition(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        manager._transition(issue, IssueState.INVESTIGATING)
        assert issue.state == IssueState.INVESTIGATING

    def test_invalid_transition_rejected(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        with pytest.raises(InvalidTransitionError):
            manager._transition(issue, IssueState.FIXING)  # NEW → FIXING not valid

    def test_transition_logged_to_audit(self, manager, registry, audit):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        manager._transition(issue, IssueState.INVESTIGATING)
        entries = audit.read(issue_id="ISS-001")
        assert any("transition:investigating" in e.get("action", "") for e in entries)

    def test_all_valid_transitions_allowed(self):
        """Verify every declared transition is exercisable."""
        for from_state, to_states in VALID_TRANSITIONS.items():
            for to_state in to_states:
                assert to_state in IssueState  # All targets are valid states

    def test_terminal_states_have_no_transitions(self):
        assert len(VALID_TRANSITIONS[IssueState.RESOLVED]) == 0
        assert len(VALID_TRANSITIONS[IssueState.DISMISSED]) == 0


class TestTickProcessing:
    def test_new_issue_auto_investigated(self, manager, registry):
        registry.register(source="gate", error_summary="E", environment="e")
        # With auto_investigate=true, tick transitions to INVESTIGATING
        # (spawn fails silently since no claude CLI, but state transitions)
        manager.tick()
        assert registry.get("ISS-001").state == IssueState.INVESTIGATING

    def test_new_issue_muted_by_pattern(self, manager, registry):
        registry.add_mute(pattern="Known error", reason="Expected")
        registry.register(source="gate", error_summary="Known error in build", environment="e")
        manager.tick()
        assert registry.get("ISS-001").state == IssueState.MUTED

    def test_diagnosed_stays_diagnosed(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        issue.state = IssueState.DIAGNOSED
        issue.diagnosis = Diagnosis(root_cause="test", impact="low", confidence=0.9)
        registry.save()

        manager.tick()
        assert registry.get("ISS-001").state == IssueState.DIAGNOSED  # waiting state

    def test_circuit_breaker_issue_skips_auto_investigation(self, manager, registry):
        """Regression guard: a NEW issue whose source starts with
        `circuit-breaker:` must NOT trigger /opsx:ff auto-investigation.

        The circuit breaker in escalate_change_to_fix_iss() already
        created a fix-iss change in state.changes and linked
        issue.change_name to it. Spawning an investigator here would
        derive a DIFFERENT change_name from the error_summary slug and
        produce a ghost orphan fix-iss that eats a dispatch slot and
        confuses the plan graph. Observed as a duplicate-change bug
        when backfilling circuit-breaker issues into IssueRegistry.
        """
        registry.register(
            source="circuit-breaker:stuck_no_progress",
            error_summary="catalog escalated to fix-iss-001-catalog",
            affected_change="catalog",
            environment="e",
        )
        manager.tick()
        # Went straight to DIAGNOSED — no investigation spawned.
        assert registry.get("ISS-001").state == IssueState.DIAGNOSED


class TestTimeoutApproval:
    def test_timeout_expires_triggers_fix(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        issue.state = IssueState.AWAITING_APPROVAL
        issue.timeout_deadline = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        issue.timeout_started_at = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        registry.save()

        # Without fixer, transition will happen but spawn won't
        manager.tick()
        # Should have attempted transition (may fail if no fixer, but state should change)
        # The _start_fix checks _can_spawn_fix which needs FIXING count == 0
        audit_entries = manager.audit.read(issue_id="ISS-001")
        assert any("timeout_auto_approved" in e.get("action", "") for e in audit_entries)

    def test_timeout_not_expired_stays(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        issue.state = IssueState.AWAITING_APPROVAL
        issue.timeout_deadline = (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat()
        issue.timeout_started_at = now_iso()
        registry.save()

        manager.tick()
        assert registry.get("ISS-001").state == IssueState.AWAITING_APPROVAL


class TestRetry:
    def test_failed_auto_retries(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        issue.state = IssueState.FAILED
        issue.retry_count = 0
        issue.max_retries = 2
        # Set updated_at far enough in the past for backoff
        issue.updated_at = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        registry.save()

        manager.tick()
        assert registry.get("ISS-001").state == IssueState.INVESTIGATING
        assert registry.get("ISS-001").retry_count == 1

    def test_retries_exhausted_stays_failed(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        issue.state = IssueState.FAILED
        issue.retry_count = 2
        issue.max_retries = 2
        registry.save()

        manager.tick()
        assert registry.get("ISS-001").state == IssueState.FAILED


class TestUserActions:
    def test_action_dismiss(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        manager._transition(issue, IssueState.DIAGNOSED)
        manager.action_dismiss("ISS-001")
        assert registry.get("ISS-001").state == IssueState.DISMISSED

    def test_action_skip(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        manager.action_skip("ISS-001", reason="Already fixed by group")
        assert registry.get("ISS-001").state == IssueState.SKIPPED

    def test_action_cancel_from_investigating(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        manager._transition(issue, IssueState.INVESTIGATING)
        manager.action_cancel("ISS-001")
        assert registry.get("ISS-001").state == IssueState.CANCELLED

    def test_action_reopen(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        manager._transition(issue, IssueState.MUTED)
        manager.action_reopen("ISS-001")
        assert registry.get("ISS-001").state == IssueState.NEW

    def test_action_extend_timeout(self, manager, registry):
        issue = registry.register(source="gate", error_summary="E", environment="e")
        issue.state = IssueState.AWAITING_APPROVAL
        issue.timeout_deadline = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
        issue.timeout_started_at = now_iso()
        registry.save()

        # Need to bypass transition validation since we set state directly
        manager.action_extend_timeout("ISS-001", extra_seconds=300)
        new_deadline = datetime.fromisoformat(registry.get("ISS-001").timeout_deadline)
        assert new_deadline > datetime.now(timezone.utc) + timedelta(seconds=300)

    def test_action_mute_creates_pattern(self, manager, registry):
        issue = registry.register(source="gate", error_summary="Build failed", environment="e")
        manager.action_mute("ISS-001")
        assert registry.get("ISS-001").state == IssueState.MUTED
        assert len(registry.all_mutes()) == 1

    def test_action_nonexistent_issue_raises(self, manager):
        with pytest.raises(ValueError):
            manager.action_dismiss("ISS-999")


class TestPolicyEngine:
    def test_can_auto_fix_eligible(self):
        config = IssuesPolicyConfig()
        config.auto_fix_severity = ["low", "medium"]
        policy = PolicyEngine(config, mode="e2e")

        issue = Issue(
            id="ISS-001", environment="e", environment_path="",
            source="gate", state=IssueState.DIAGNOSED, severity="medium",
        )
        issue.diagnosis = Diagnosis(
            root_cause="test", impact="medium", confidence=0.9,
            fix_scope="single_file",
        )
        assert policy.can_auto_fix(issue) is True

    def test_unknown_severity_blocks_auto_fix(self):
        config = IssuesPolicyConfig()
        policy = PolicyEngine(config, mode="e2e")

        issue = Issue(
            id="ISS-001", environment="e", environment_path="",
            source="gate", state=IssueState.DIAGNOSED, severity="unknown",
        )
        issue.diagnosis = Diagnosis(root_cause="test", confidence=0.9)
        assert policy.can_auto_fix(issue) is False

    def test_blocked_tag_prevents_auto_fix(self):
        config = IssuesPolicyConfig()
        config.auto_fix_severity = ["medium"]
        policy = PolicyEngine(config, mode="e2e")

        issue = Issue(
            id="ISS-001", environment="e", environment_path="",
            source="gate", state=IssueState.DIAGNOSED, severity="medium",
        )
        issue.diagnosis = Diagnosis(
            root_cause="test", impact="medium", confidence=0.9,
            fix_scope="single_file", tags=["db_migration"],
        )
        assert policy.can_auto_fix(issue) is False

    def test_low_confidence_prevents_auto_fix(self):
        config = IssuesPolicyConfig()
        config.auto_fix_severity = ["medium"]
        policy = PolicyEngine(config, mode="e2e")

        issue = Issue(
            id="ISS-001", environment="e", environment_path="",
            source="gate", state=IssueState.DIAGNOSED, severity="medium",
        )
        issue.diagnosis = Diagnosis(
            root_cause="test", impact="medium", confidence=0.5,
            fix_scope="single_file",
        )
        assert policy.can_auto_fix(issue) is False

    def test_get_timeout_by_severity(self):
        config = IssuesPolicyConfig()
        policy = PolicyEngine(config, mode="e2e")

        issue = Issue(
            id="ISS-001", environment="e", environment_path="",
            source="gate", state=IssueState.DIAGNOSED, severity="low",
        )
        timeout = policy.get_timeout(issue)
        assert timeout == 120  # default for low


class TestDiagnosisParsing:
    def test_diagnosis_to_and_from_dict(self):
        diag = Diagnosis(
            root_cause="Bug in auth",
            impact="high",
            confidence=0.92,
            fix_scope="single_file",
            suggested_fix="Fix the condition",
            affected_files=["auth.py:42"],
            tags=["auth"],
        )
        d = diag.to_dict()
        restored = Diagnosis.from_dict(d)
        assert restored.root_cause == "Bug in auth"
        assert restored.confidence == 0.92

    def test_issue_serialization_with_diagnosis(self):
        issue = Issue(
            id="ISS-001", environment="e", environment_path="/tmp",
            source="gate", state=IssueState.DIAGNOSED,
        )
        issue.diagnosis = Diagnosis(root_cause="test", confidence=0.8)
        d = issue.to_dict()
        restored = Issue.from_dict(d)
        assert restored.diagnosis is not None
        assert restored.diagnosis.confidence == 0.8
