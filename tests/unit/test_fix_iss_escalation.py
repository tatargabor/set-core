"""Unit tests for fix-iss auto-escalation (section 10 of
fix-replan-stuck-gate-and-decomposer).

Covers the module-level helper `escalate_change_to_fix_iss` already
exercised indirectly by the stuck-loop and token-runaway breakers.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.issues.manager import (  # noqa: E402
    escalate_change_to_fix_iss, _classify_fix_target,
)
from set_orch.state import Change, OrchestratorState, load_state, save_state  # noqa: E402


class _Bus:
    def __init__(self): self.events = []
    def emit(self, typ, **kw): self.events.append((typ, kw))


@pytest.fixture
def state_file(tmp_path):
    os.makedirs(tmp_path / "openspec" / "changes", exist_ok=True)
    sf = tmp_path / "state.json"
    save_state(OrchestratorState(
        status="running",
        changes=[Change(name="parent", status="failed", input_tokens=5_000_000,
                        token_runaway_baseline=1_000_000)],
    ), str(sf))
    return str(sf)


def test_framework_path_target():
    assert _classify_fix_target(["lib/set_orch/engine.py"]) == "framework"
    assert _classify_fix_target(["modules/web/gates.py"]) == "framework"
    assert _classify_fix_target([".claude/rules/x.md"]) == "framework"


def test_consumer_path_target():
    assert _classify_fix_target(["src/app/page.tsx"]) == "consumer"
    assert _classify_fix_target([]) == "consumer"


def test_escalation_creates_proposal_and_updates_parent(state_file, tmp_path):
    bus = _Bus()
    new_name = escalate_change_to_fix_iss(
        state_file=state_file,
        change_name="parent",
        stop_gate="review",
        findings=[{"file": "lib/set_orch/engine.py"}],
        escalation_reason="retry_budget_exhausted",
        event_bus=bus,
    )
    assert new_name.startswith("fix-iss-")
    assert "parent" in new_name
    proposal = tmp_path / "openspec" / "changes" / new_name / "proposal.md"
    assert proposal.is_file()
    text = proposal.read_text()
    for heading in ("Why", "What Changes", "Capabilities", "Impact", "Fix Target"):
        assert heading in text
    assert "framework" in text  # because the finding path is under lib/set_orch/

    # parent.fix_iss_child is set
    st = load_state(state_file)
    parent = next(c for c in st.changes if c.name == "parent")
    assert parent.fix_iss_child == new_name

    # Event emitted
    assert any(t == "FIX_ISS_ESCALATED" for t, _ in bus.events)


def test_escalation_token_runaway_includes_runaway_section(state_file, tmp_path):
    new_name = escalate_change_to_fix_iss(
        state_file=state_file,
        change_name="parent",
        stop_gate="",
        findings=[],
        escalation_reason="token_runaway",
        event_bus=None,
    )
    text = (tmp_path / "openspec" / "changes" / new_name / "proposal.md").read_text()
    assert "Runaway metadata" in text
    assert "baseline" in text
    assert "current input_tokens" in text
    assert "delta" in text


def test_successive_escalations_are_idempotent(state_file):
    """Per fix-iss-lifecycle-hardening: one parent → one active fix-iss child.
    Re-escalating while the first child is still live returns the same name
    (no duplicate escalations)."""
    n1 = escalate_change_to_fix_iss(
        state_file=state_file, change_name="parent",
        stop_gate="review", findings=[],
        escalation_reason="retry_budget_exhausted",
    )
    n2 = escalate_change_to_fix_iss(
        state_file=state_file, change_name="parent",
        stop_gate="review", findings=[],
        escalation_reason="retry_budget_exhausted",
    )
    # Idempotent: second call returns the existing child name
    assert n1 == n2


def test_escalation_increments_when_prior_child_gone(state_file, tmp_path):
    """When the prior fix-iss child is purged (state entry removed + dir gone),
    re-escalation auto-repairs the stale link and creates a fresh child."""
    import shutil
    from set_orch.state import load_state, locked_state

    n1 = escalate_change_to_fix_iss(
        state_file=state_file, change_name="parent",
        stop_gate="review", findings=[],
        escalation_reason="retry_budget_exhausted",
    )
    # Simulate an operator-driven purge: remove the dir and the state entry.
    shutil.rmtree(tmp_path / "openspec" / "changes" / n1)
    with locked_state(state_file) as s:
        s.changes = [c for c in s.changes if c.name != n1]

    n2 = escalate_change_to_fix_iss(
        state_file=state_file, change_name="parent",
        stop_gate="review", findings=[],
        escalation_reason="retry_budget_exhausted",
    )
    # Fresh escalation produces a new child (same NNN reused since dir is gone)
    assert n2.startswith("fix-iss-")
    # Parent's fix_iss_child link updated to the new name
    st = load_state(state_file)
    parent = next(c for c in st.changes if c.name == "parent")
    assert parent.fix_iss_child == n2


def test_escalation_registers_fix_iss_in_state(state_file):
    """Task 10.7 — fix-iss is added to state.changes so the dispatcher
    picks it up on the next monitor poll."""
    new_name = escalate_change_to_fix_iss(
        state_file=state_file, change_name="parent",
        stop_gate="review",
        findings=[{"file": "lib/set_orch/engine.py"}],
        escalation_reason="retry_budget_exhausted",
    )
    st = load_state(state_file)
    fix_iss = next((c for c in st.changes if c.name == new_name), None)
    assert fix_iss is not None, "fix-iss not appended to state.changes"
    assert fix_iss.status == "pending"
    # Phase is bumped past the parent so the fix-iss runs after — the
    # parent's phase default is 1 in the fixture.
    parent = next(c for c in st.changes if c.name == "parent")
    assert fix_iss.phase == parent.phase + 1
    assert parent.name in (fix_iss.depends_on or [])


def test_escalation_idempotent_on_repeat_call(state_file):
    """Re-invoking escalate with the same name does not duplicate the change."""
    # Force the same fix-iss name by checking state after first call
    n1 = escalate_change_to_fix_iss(
        state_file=state_file, change_name="parent",
        stop_gate="review", findings=[],
        escalation_reason="retry_budget_exhausted",
    )
    st1 = load_state(state_file)
    count1 = sum(1 for c in st1.changes if c.name == n1)
    assert count1 == 1

    # Manually call the registration helper again — should be a no-op
    from set_orch.issues.manager import _register_fix_iss_in_state
    _register_fix_iss_in_state(state_file, "parent", n1, "framework")
    st2 = load_state(state_file)
    count2 = sum(1 for c in st2.changes if c.name == n1)
    assert count2 == 1


def test_escalation_links_issue_change_name_to_existing_fix_iss(state_file, tmp_path):
    """The IssueRegistry entry created by the escalation must carry
    `change_name = <the real fix-iss name>` so a downstream
    IssueManager tick cannot spawn /opsx:ff against a ghost duplicate
    change derived from the error_summary slug.

    Observed bug: without the link, when IssueManager processes the
    NEW issue and auto-investigates, `investigator.spawn()` generates
    change_name = f"fix-{issue.id}-{_slugify(issue.error_summary)}"
    which drifts from the real fix-iss name, leaving a dead
    investigation AND a useless orphan change in state.changes.
    """
    from set_orch.issues.registry import IssueRegistry

    fix_iss_name = escalate_change_to_fix_iss(
        state_file=state_file, change_name="parent",
        stop_gate="review", findings=[],
        escalation_reason="stuck_no_progress",
    )

    reg = IssueRegistry(tmp_path)
    issues = reg.all_issues()
    assert len(issues) == 1
    # Source marks this as a circuit-breaker escalation.
    assert issues[0].source == "circuit-breaker:stuck_no_progress"
    # And the issue is linked to the REAL fix-iss change, not a slug.
    assert issues[0].change_name == fix_iss_name
    assert issues[0].affected_change == "parent"
