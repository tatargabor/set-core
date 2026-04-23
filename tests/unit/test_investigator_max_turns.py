"""Unit tests for InvestigationRunner's `--max-turns` plumbing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from set_orch.issues.audit import AuditLog
from set_orch.issues.investigator import InvestigationRunner
from set_orch.issues.models import Issue, IssueState
from set_orch.issues.policy import IssuesPolicyConfig, InvestigationConfig


def _make_runner(tmp_path: Path, max_turns: int | None = None) -> InvestigationRunner:
    config = IssuesPolicyConfig()
    if max_turns is not None:
        config.investigation = InvestigationConfig(max_turns=max_turns)
    audit = AuditLog(tmp_path)
    return InvestigationRunner(
        set_core_path=tmp_path,
        config=config,
        audit=audit,
    )


def _make_issue(env_path: Path) -> Issue:
    return Issue(
        id="ISS-001",
        environment="test",
        environment_path=str(env_path),
        source="gate",
        state=IssueState.NEW,
        error_summary="failure",
        error_detail="some error",
        affected_change=None,
    )


def test_spawn_uses_default_max_turns_40(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path)
    issue = _make_issue(tmp_path)
    with patch("set_orch.issues.investigator.subprocess.Popen") as popen_mock:
        popen_mock.return_value.pid = 12345
        runner.spawn(issue)
    cmd = popen_mock.call_args[0][0]
    assert "--max-turns" in cmd
    idx = cmd.index("--max-turns")
    assert cmd[idx + 1] == "40"


def test_spawn_honors_override_max_turns_60(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, max_turns=60)
    issue = _make_issue(tmp_path)
    with patch("set_orch.issues.investigator.subprocess.Popen") as popen_mock:
        popen_mock.return_value.pid = 12345
        runner.spawn(issue)
    cmd = popen_mock.call_args[0][0]
    idx = cmd.index("--max-turns")
    assert cmd[idx + 1] == "60"


def test_spawn_honors_override_max_turns_30(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, max_turns=30)
    issue = _make_issue(tmp_path)
    with patch("set_orch.issues.investigator.subprocess.Popen") as popen_mock:
        popen_mock.return_value.pid = 11111
        runner.spawn(issue)
    cmd = popen_mock.call_args[0][0]
    idx = cmd.index("--max-turns")
    assert cmd[idx + 1] == "30"
