"""Unit tests for lib/set_orch/gate_verdict.py.

Covers:
- snapshot/find_new_session_file basic flow
- purpose-marker disambiguation between concurrent sessions
- GateVerdict round-trip (write → read)
- to_outcome() mapping
- read_verdict_sidecar handles missing/corrupt files
- persist_gate_verdict end-to-end (mocked Home dir)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.gate_verdict import (
    GateVerdict,
    claude_session_dir,
    find_new_session_file,
    persist_gate_verdict,
    read_verdict_sidecar,
    snapshot_session_files,
    write_verdict_sidecar,
    _claude_mangle,
)


@pytest.fixture
def fake_home(monkeypatch):
    """Redirect Path.home() to a temp dir so the tests don't pollute ~/.claude."""
    d = tempfile.mkdtemp()
    monkeypatch.setenv("HOME", d)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path(d)))
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def cwd_with_session_dir(fake_home):
    """Create a fake worktree path AND its claude session dir under fake_home."""
    cwd = "/home/me/worktree-foo"
    session_dir = claude_session_dir(cwd)
    session_dir.mkdir(parents=True, exist_ok=True)
    return cwd, session_dir


def _write_session(session_dir: Path, name: str, marker: str = "") -> Path:
    """Drop a fake session jsonl with an optional [PURPOSE:...] marker."""
    f = session_dir / f"{name}.jsonl"
    body = {
        "type": "queue-operation",
        "content": f"{marker}\nrest of prompt\n",
    }
    f.write_text(json.dumps(body) + "\n")
    return f


# ─── _claude_mangle ───────────────────────────────────────


def test_mangle_strips_leading_slash():
    assert _claude_mangle("/home/me/wt") == "home-me-wt"


def test_mangle_replaces_slash_dot_underscore():
    assert _claude_mangle("/home/me_user/code.dir/foo") == "home-me-user-code-dir-foo"


# ─── snapshot + find_new ──────────────────────────────────


class TestSnapshotAndFind:
    def test_snapshot_empty_dir(self, cwd_with_session_dir):
        cwd, _ = cwd_with_session_dir
        assert snapshot_session_files(cwd) == set()

    def test_snapshot_missing_dir(self, fake_home):
        # No session dir at all
        assert snapshot_session_files("/some/path/that/does/not/exist") == set()

    def test_snapshot_lists_existing_jsonl_only(self, cwd_with_session_dir):
        cwd, sd = cwd_with_session_dir
        _write_session(sd, "abc-123")
        _write_session(sd, "def-456")
        # Non-jsonl files must not appear
        (sd / "notes.txt").write_text("ignore me")
        snap = snapshot_session_files(cwd)
        assert snap == {"abc-123", "def-456"}

    def test_find_new_picks_session_added_after_baseline(self, cwd_with_session_dir):
        cwd, sd = cwd_with_session_dir
        _write_session(sd, "old-session")
        baseline = snapshot_session_files(cwd)
        new = _write_session(sd, "new-session")
        found = find_new_session_file(cwd, baseline)
        assert found == new

    def test_find_new_returns_none_when_no_new_session(self, cwd_with_session_dir):
        cwd, sd = cwd_with_session_dir
        _write_session(sd, "only-one")
        baseline = snapshot_session_files(cwd)
        assert find_new_session_file(cwd, baseline) is None

    def test_find_new_disambiguates_via_purpose_marker(self, cwd_with_session_dir):
        cwd, sd = cwd_with_session_dir
        baseline = snapshot_session_files(cwd)
        # Two new sessions land between snapshot and check.
        review_session = _write_session(sd, "uuid-review", marker="[PURPOSE:review:my-change]")
        # Touch with newer mtime so without marker disambiguation we'd pick this one
        other_session = _write_session(sd, "uuid-build", marker="[PURPOSE:build_fix:other]")
        os.utime(other_session, (other_session.stat().st_mtime + 5, other_session.stat().st_mtime + 5))

        # Without marker we'd get the newer (build_fix) session
        without = find_new_session_file(cwd, baseline)
        assert without == other_session

        # With marker we always get the review session
        with_marker = find_new_session_file(
            cwd, baseline, purpose_marker="[PURPOSE:review:my-change]",
        )
        assert with_marker == review_session

    def test_find_new_returns_none_when_marker_matches_nothing(self, cwd_with_session_dir):
        cwd, sd = cwd_with_session_dir
        baseline = snapshot_session_files(cwd)
        _write_session(sd, "u1", marker="[PURPOSE:review:other]")
        assert find_new_session_file(
            cwd, baseline, purpose_marker="[PURPOSE:review:not-this-one]",
        ) is None


# ─── GateVerdict + sidecar I/O ────────────────────────────


class TestGateVerdictIO:
    def test_round_trip(self, tmp_path):
        session = tmp_path / "abc.jsonl"
        session.write_text("{}\n")
        v = GateVerdict(
            gate="review",
            verdict="fail",
            critical_count=2,
            high_count=1,
            source="classifier_override",
            change="my-change",
            summary="2 critical findings via classifier",
        )
        write_verdict_sidecar(session, v)

        sidecar = session.with_name("abc.verdict.json")
        assert sidecar.is_file()
        assert "tmp" not in sidecar.name  # tmp file got renamed away

        loaded = read_verdict_sidecar(session)
        assert loaded is not None
        assert loaded.gate == "review"
        assert loaded.verdict == "fail"
        assert loaded.critical_count == 2
        assert loaded.high_count == 1
        assert loaded.source == "classifier_override"
        assert loaded.change == "my-change"

    def test_missing_sidecar_returns_none(self, tmp_path):
        session = tmp_path / "no-sidecar.jsonl"
        session.write_text("{}\n")
        assert read_verdict_sidecar(session) is None

    def test_corrupt_sidecar_returns_none(self, tmp_path):
        session = tmp_path / "u.jsonl"
        session.write_text("{}\n")
        sidecar = session.with_name("u.verdict.json")
        sidecar.write_text("{not valid json")
        assert read_verdict_sidecar(session) is None

    def test_unknown_fields_dropped(self, tmp_path):
        session = tmp_path / "u.jsonl"
        session.write_text("{}\n")
        sidecar = session.with_name("u.verdict.json")
        sidecar.write_text(json.dumps({
            "gate": "review",
            "verdict": "pass",
            "future_field": "ignore me",
        }))
        v = read_verdict_sidecar(session)
        assert v is not None
        assert v.gate == "review"
        assert v.verdict == "pass"

    def test_to_outcome(self):
        assert GateVerdict(gate="review", verdict="pass").to_outcome() == "success"
        assert GateVerdict(gate="review", verdict="fail").to_outcome() == "error"
        assert GateVerdict(gate="review", verdict="?").to_outcome() == "unknown"


# ─── persist_gate_verdict end-to-end ──────────────────────


class TestPersistGateVerdict:
    def test_picks_new_session_and_writes_sidecar(self, cwd_with_session_dir):
        cwd, sd = cwd_with_session_dir
        baseline = snapshot_session_files(cwd)
        # Simulate Claude creating a new session jsonl
        new_session = _write_session(sd, "abc-uuid", marker="[PURPOSE:review:my-change]")

        result = persist_gate_verdict(
            cwd=cwd,
            baseline=baseline,
            change_name="my-change",
            gate="review",
            verdict="pass",
            critical_count=0,
            source="classifier_confirmed",
            summary="0 critical (verified)",
        )
        assert result == new_session
        sidecar = new_session.with_name("abc-uuid.verdict.json")
        assert sidecar.is_file()
        v = read_verdict_sidecar(new_session)
        assert v is not None
        assert v.verdict == "pass"
        assert v.source == "classifier_confirmed"

    def test_returns_none_when_no_new_session(self, cwd_with_session_dir):
        cwd, sd = cwd_with_session_dir
        _write_session(sd, "pre-existing", marker="[PURPOSE:review:my-change]")
        baseline = snapshot_session_files(cwd)
        # No new session — Claude exec failed before file creation
        result = persist_gate_verdict(
            cwd=cwd,
            baseline=baseline,
            change_name="my-change",
            gate="review",
            verdict="pass",
            source="exec_failed",
        )
        assert result is None

    def test_marker_filters_out_concurrent_unrelated_session(self, cwd_with_session_dir):
        cwd, sd = cwd_with_session_dir
        baseline = snapshot_session_files(cwd)
        review_session = _write_session(sd, "review-uuid", marker="[PURPOSE:review:change-a]")
        # A second concurrent session for a different gate / change appears too
        _write_session(sd, "build-uuid", marker="[PURPOSE:build_fix:change-b]")

        result = persist_gate_verdict(
            cwd=cwd,
            baseline=baseline,
            change_name="change-a",
            gate="review",
            verdict="fail",
            critical_count=1,
            source="fast_path",
        )
        assert result == review_session
        sidecar = review_session.with_name("review-uuid.verdict.json")
        assert sidecar.is_file()
        # The build_fix session must NOT have a sidecar
        assert not (sd / "build-uuid.verdict.json").exists()
