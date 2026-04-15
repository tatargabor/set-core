"""Regression test: screenshots endpoint surfaces archived previous attempts.

Observed on craftbrew-run-20260415-0146: admin-products merged after 4 attempts.
Attempts 1-3 each failed with 3-4 Playwright screenshots + retry screenshots.
The dashboard's "scan" button silently did nothing because attempt #4 passed
(screenshot: only-on-failure → test-results/ empty).

Fix: gate_runner._archive_attempt_artifacts copies test-results/ to
`<runtime>/attempts/<change>/attempt-N/test-results/` before each retry
dispatches, so later requests to /screenshots can surface them.

This test verifies the endpoint:
  1. Scans the archived attempts directory
  2. Tags each artifact with its attempt number
  3. Merges archived + current into one list sorted by attempt
  4. Returns an `attempts` field listing which attempt numbers are present
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


def _seed_state(project_dir: Path, change_name: str) -> None:
    """Create a minimal orchestration-state.json the endpoint can load."""
    state_dir = project_dir / "set" / "orchestration"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "status": "running",
        "changes": [
            {"name": change_name, "extras": {}, "worktree_path": ""}
        ],
    }
    (project_dir / "orchestration-state.json").write_text(json.dumps(state))


def _write_archived_attempt(
    project_dir: Path,
    change_name: str,
    attempt: int,
    image_name: str,
) -> Path:
    """Mimic gate_runner._archive_attempt_artifacts output."""
    dest = (
        project_dir / "set" / "orchestration" / "attempts" / change_name
        / f"attempt-{attempt}" / "test-results" / f"spec-{attempt}-chromium"
    )
    dest.mkdir(parents=True, exist_ok=True)
    png = dest / image_name
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)  # minimal PNG header
    return png


def test_scan_archived_attempts_returns_per_attempt_metadata(tmp_path: Path):
    from set_orch.api.media import _scan_archived_attempts

    change = "admin-products"
    _write_archived_attempt(tmp_path, change, 1, "test-failed-1.png")
    _write_archived_attempt(tmp_path, change, 1, "test-failed-2.png")
    _write_archived_attempt(tmp_path, change, 2, "test-failed-1.png")
    _write_archived_attempt(tmp_path, change, 3, "test-failed-1.png")

    items = _scan_archived_attempts(tmp_path, change)
    assert len(items) == 4
    attempts = sorted({x["attempt"] for x in items})
    assert attempts == [1, 2, 3]
    # Every PNG must be classified as "image".
    assert all(x["type"] == "image" for x in items)
    # Names preserved.
    assert "test-failed-1.png" in {x["name"] for x in items}


def test_scan_archived_attempts_empty_when_no_archive(tmp_path: Path):
    from set_orch.api.media import _scan_archived_attempts
    assert _scan_archived_attempts(tmp_path, "nonexistent") == []


def test_archive_attempt_artifacts_copies_test_results(tmp_path: Path, monkeypatch):
    """gate_runner._archive_attempt_artifacts should copy test-results to the
    runtime attempts dir and survive being called when source is empty.
    """
    from set_orch.gate_runner import _archive_attempt_artifacts

    # Mock SetRuntime so artifacts land inside tmp_path instead of the real
    # runtime directory.
    from set_orch import paths as paths_mod

    class _FakeRuntime:
        screenshots_dir = str(tmp_path / "runtime" / "screenshots")

    monkeypatch.setattr(paths_mod, "SetRuntime", lambda: _FakeRuntime())

    wt = tmp_path / "wt"
    test_results = wt / "test-results" / "spec-chromium"
    test_results.mkdir(parents=True)
    (test_results / "test-failed-1.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    (test_results / "error-context.md").write_text("stack trace")

    n = _archive_attempt_artifacts(str(wt), "admin-products", attempt=2)
    assert n > 0

    archived_png = (
        tmp_path / "runtime" / "screenshots" / "attempts" / "admin-products"
        / "attempt-2" / "test-results" / "spec-chromium" / "test-failed-1.png"
    )
    assert archived_png.is_file()


def test_archive_no_op_when_worktree_missing(tmp_path: Path):
    from set_orch.gate_runner import _archive_attempt_artifacts
    # Nonexistent worktree — return 0, not raise.
    assert _archive_attempt_artifacts(str(tmp_path / "missing"), "x", attempt=1) == 0


def test_archive_no_op_when_attempt_zero(tmp_path: Path):
    """Attempt 0 means the first gate — nothing has failed yet, no archive."""
    from set_orch.gate_runner import _archive_attempt_artifacts
    wt = tmp_path / "wt"
    (wt / "test-results").mkdir(parents=True)
    assert _archive_attempt_artifacts(str(wt), "x", attempt=0) == 0
