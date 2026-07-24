"""A finding must not be consumed by a registration that never happened.

`DetectionBridge` keeps a `processed_findings` set so a finding is turned into an
issue exactly once. The set is the only guard: a key in it is skipped on every later
scan, forever. So what puts a key in it decides whether a transient failure costs one
retry or the finding itself.

It used to be recorded before `register()` ran. An unwritable registry, a corrupt
JSON, a full disk — the finding was consumed anyway, stayed `open` in findings.json,
and nothing would ever look at it again. Measured on a consumer tree: 18 findings
consumed, 10 issues registered, and the 8 missing ones unrecoverable without editing
state by hand.

A returned `None` is the opposite case and legitimate: muted, duplicate, or below the
policy threshold. That DOES consume the finding — muting a finding you keep re-reading
is not muting.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.issues.detector import DetectionBridge  # noqa: E402
from set_orch import paths as set_paths  # noqa: E402
from set_orch.paths import SetRuntime  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """SetRuntime resolves findings.json under a shared per-user data dir.

    Without this every test in the process writes the same findings.json, so the
    suite passes alone and fails next to anything else that touches it.
    """
    monkeypatch.setattr(set_paths, "SET_TOOLS_DATA_DIR", str(tmp_path / "runtime"))


class _Manager:
    """Stand-in IssueManager: replays a scripted outcome per call."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def register(self, **kwargs):
        self.calls.append(kwargs.get("source_finding_id"))
        outcome = self.outcomes.pop(0) if self.outcomes else object()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _write_findings(proj: Path, findings):
    """Put findings.json wherever SetRuntime resolves it for this project."""
    path = Path(SetRuntime(str(proj)).sentinel_dir) / "findings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"findings": findings}))
    return path


@pytest.fixture
def project(tmp_path):
    """A project whose sentinel dir holds one open finding."""
    proj = tmp_path / "proj"
    proj.mkdir()
    _write_findings(proj, [
        {"id": "F001", "status": "open", "severity": "high", "summary": "boom"},
    ])
    return proj


def _detector(manager, state_dir, project):
    return DetectionBridge(manager, projects={"proj": {"path": project}},
                           state_dir=state_dir)


def _processed(state_dir):
    path = state_dir / "processed_findings.json"
    return set(json.loads(path.read_text())) if path.exists() else set()


def test_failed_registration_leaves_the_finding_retryable(tmp_path, project):
    state = tmp_path / "state"
    manager = _Manager([RuntimeError("registry unwritable")])
    _detector(manager, state, project).scan_all_projects()

    assert "proj:F001" not in _processed(state), \
        "an exception consumed the finding — it can never be registered again"


def test_the_next_scan_actually_retries_it(tmp_path, project):
    """The real cost of the bug: not one lost write, but every later one."""
    state = tmp_path / "state"
    manager = _Manager([RuntimeError("transient"), object()])

    _detector(manager, state, project).scan_all_projects()
    _detector(manager, state, project).scan_all_projects()

    assert manager.calls == ["F001", "F001"]
    assert "proj:F001" in _processed(state), "the successful retry must stick"


def test_successful_registration_consumes_the_finding(tmp_path, project):
    state = tmp_path / "state"
    manager = _Manager([object()])
    _detector(manager, state, project).scan_all_projects()

    assert "proj:F001" in _processed(state)


def test_a_declined_registration_still_consumes_it(tmp_path, project):
    """None means muted or below threshold — a deliberate decision, not a failure.

    Re-reading a muted finding on every scan is not muting.
    """
    state = tmp_path / "state"
    manager = _Manager([None])
    _detector(manager, state, project).scan_all_projects()

    assert "proj:F001" in _processed(state)


def test_a_failure_does_not_abandon_the_remaining_findings(tmp_path):
    """One bad finding must not end the scan for everything after it."""
    proj = tmp_path / "proj"
    proj.mkdir()
    _write_findings(proj, [
        {"id": "F001", "status": "open", "summary": "first"},
        {"id": "F002", "status": "open", "summary": "second"},
    ])
    state = tmp_path / "state"
    manager = _Manager([RuntimeError("boom"), object()])

    _detector(manager, state, proj).scan_all_projects()

    assert manager.calls == ["F001", "F002"]
    assert _processed(state) == {"proj:F002"}


def test_a_declined_finding_is_logged_not_left_to_be_inferred(tmp_path, project, caplog):
    """The gap between two state files is not a reporting mechanism.

    A consumer found this defect by noticing processed_findings.json and
    registry.json had drifted apart. That should have been a log line.
    """
    state = tmp_path / "state"
    with caplog.at_level("INFO"):
        _detector(_Manager([None]), state, project).scan_all_projects()

    assert any("F001" in r.message for r in caplog.records)


def test_a_failed_registration_is_logged_at_warning(tmp_path, project, caplog):
    state = tmp_path / "state"
    with caplog.at_level("WARNING"):
        _detector(_Manager([OSError("disk full")]), state, project).scan_all_projects()

    assert any("F001" in r.message and r.levelname == "WARNING" for r in caplog.records)
