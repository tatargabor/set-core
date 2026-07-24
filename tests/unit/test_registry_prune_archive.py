"""Archiving, preview mode, the backup, and the confirmation — the parts of the
prune that decide whether an operator can undo it.

Archiving exists because the loss-free constraint forbids deregistering a project
whose directory is alive. What it must never become is a quiet way to hide a
broken project, so the refusals are tested as carefully as the successes.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import project_registry  # noqa: E402
from set_orch import registry_prune as rp  # noqa: E402


@pytest.fixture
def reg(tmp_path, monkeypatch):
    """A registry with one real project and two E2E runs — one old, one recent."""
    home = tmp_path / "home"
    (home / ".config" / "set-core").mkdir(parents=True)
    registry = home / ".config" / "set-core" / "projects.json"
    e2e_root = tmp_path / "e2e-runs"

    old_run = e2e_root / "old-run"
    new_run = e2e_root / "new-run"
    real = tmp_path / "real-project"
    for d in (old_run, new_run, real):
        d.mkdir(parents=True)

    ancient = time.time() - 200 * 86400
    os.utime(old_run, (ancient, ancient))
    os.utime(real, (ancient, ancient))   # a real project exactly as old

    registry.write_text(json.dumps({
        "projects": {
            "old-run": {"path": str(old_run), "addedAt": "2026-01-01", "project_type": "web"},
            "new-run": {"path": str(new_run), "addedAt": "2026-01-01"},
            "real-project": {"path": str(real), "addedAt": "2026-01-01"},
        },
    }, indent=2))

    monkeypatch.setattr(project_registry, "PROJECTS_FILE", registry)
    monkeypatch.setattr(rp, "e2e_runs_root", lambda: e2e_root)
    return {"registry": registry, "e2e_root": e2e_root, "old": old_run,
            "new": new_run, "real": real}


def _entries(registry: Path) -> dict:
    return json.loads(registry.read_text())["projects"]


def _write_issues(project: Path, payload) -> None:
    """Write an issue registry and re-age the project.

    Creating the file bumps the directory's mtime, which is what the age check
    reads — so without this the fixture would silently stop being old and the
    refusal under test would never be reached.
    """
    issues = project / ".set" / "issues"
    issues.mkdir(parents=True, exist_ok=True)
    (issues / "registry.json").write_text(
        payload if isinstance(payload, str) else json.dumps(payload)
    )
    ancient = time.time() - 200 * 86400
    os.utime(project, (ancient, ancient))


# ─── The two conditions ───────────────────────────────────────────────


def test_a_bare_prune_archives_nothing(reg):
    """AC-10. No default threshold exists, so the plain command cannot archive."""
    report = rp.run_prune(preview=False)
    assert report.archived == []
    assert all("archived" not in e for e in _entries(reg["registry"]).values())


def test_an_old_project_outside_the_e2e_root_is_not_archived(reg):
    """AC-11. Location is the separator, not age: this project is exactly as old
    as `old-run` and must survive untouched."""
    report = rp.run_prune(preview=False, archive_older_than="30d")
    assert "real-project" not in report.archived
    assert "archived" not in _entries(reg["registry"])["real-project"]
    assert report.archived == ["old-run"]


def test_a_recent_e2e_run_is_not_archived(reg):
    """AC-12."""
    report = rp.run_prune(preview=False, archive_older_than="30d")
    assert "new-run" not in report.archived


def test_an_unparsable_threshold_raises_rather_than_defaulting(reg):
    with pytest.raises(ValueError):
        rp.run_prune(preview=True, archive_older_than="soon")


# ─── Archive semantics ────────────────────────────────────────────────


def test_archiving_does_not_deregister(reg):
    """AC-9."""
    rp.run_prune(preview=False, archive_older_than="30d")
    entry = _entries(reg["registry"])["old-run"]
    assert entry["archived"] is True
    assert entry["path"] == str(reg["old"])
    assert reg["old"].is_dir()


def test_archive_is_reversible(reg):
    """AC-8. Clearing the flag restores the entry exactly — no field lost, none
    added. A one-way "archive" would be a delete wearing a softer name."""
    before = dict(_entries(reg["registry"])["old-run"])
    entry = dict(before)
    rp.apply_archive(entry)
    assert entry["archived"] is True and entry["archivedAt"]
    rp.clear_archive(entry)
    assert entry == before


# ─── Refusals: nothing broken gets hidden ─────────────────────────────


def test_open_issues_block_archiving(reg):
    """AC-13. `ui-quality.md`: compacting must never hide a failure. An archived
    project leaves the overview, so it may not leave with an open issue."""
    _write_issues(reg["old"], {"issues": [{"id": "ISS-001", "state": "failed"}]})

    report = rp.run_prune(preview=False, archive_older_than="30d")
    assert report.archived == []
    assert [r.name for r in report.archive_refused] == ["old-run"]
    assert "1 open issue" in report.archive_refused[0].reason


def test_a_closed_issue_does_not_block_archiving(reg):
    """The refusal must discriminate, or it degrades to "never archive"."""
    _write_issues(reg["old"], {"issues": [{"id": "ISS-001", "state": "resolved"}]})
    report = rp.run_prune(preview=False, archive_older_than="30d")
    assert report.archived == ["old-run"]


def test_an_unreadable_issue_registry_blocks_archiving(reg):
    """A gap is not a zero. Unparseable means unknown, and unknown must not read
    as "no open issues" — the direction of that error hides a failure."""
    _write_issues(reg["old"], "{ truncated")
    report = rp.run_prune(preview=False, archive_older_than="30d")
    assert report.archived == []
    assert "unreadable" in report.archive_refused[0].reason


def test_a_live_process_blocks_archiving(reg, monkeypatch):
    """AC-14."""
    monkeypatch.setattr(rp, "_live_process", lambda p: "sentinel" if p == reg["old"] else None)
    report = rp.run_prune(preview=False, archive_older_than="30d")
    assert report.archived == []
    assert "sentinel is running" in report.archive_refused[0].reason


# ─── Preview writes nothing ───────────────────────────────────────────


def test_a_preview_leaves_the_registry_untouched(tmp_path, monkeypatch):
    """AC-15. Content AND mtime, plus the absence of a backup file: a dry run
    that quietly wrote a backup would still be a write."""
    home = tmp_path / "home"
    (home / ".config" / "set-core").mkdir(parents=True)
    registry = home / ".config" / "set-core" / "projects.json"
    registry.write_text(json.dumps({"projects": {
        "gone": {"path": str(tmp_path / "gone")},
    }}, indent=2))
    monkeypatch.setattr(project_registry, "PROJECTS_FILE", registry)

    before_bytes = registry.read_bytes()
    before_mtime = registry.stat().st_mtime_ns
    time.sleep(0.01)

    report = rp.run_prune(preview=True)
    assert report.deregistered == ["gone"]      # it did find the work
    assert report.preview is True

    assert registry.read_bytes() == before_bytes
    assert registry.stat().st_mtime_ns == before_mtime
    assert list(registry.parent.glob("*.bak-*")) == []
    assert report.backup_path is None


# ─── Backup precedes mutation ─────────────────────────────────────────


def test_backup_precedes_mutation(tmp_path, monkeypatch):
    """AC-16. The backup must hold the PRE-prune content — a backup refreshed by
    the operation it protects against is not a backup."""
    home = tmp_path / "home"
    (home / ".config" / "set-core").mkdir(parents=True)
    registry = home / ".config" / "set-core" / "projects.json"
    original = json.dumps({"projects": {"gone": {"path": str(tmp_path / "gone")}}}, indent=2)
    registry.write_text(original)
    monkeypatch.setattr(project_registry, "PROJECTS_FILE", registry)

    report = rp.run_prune(preview=False)
    backups = list(registry.parent.glob("projects.json.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == original
    assert report.backup_path == str(backups[0])
    assert "gone" not in json.loads(registry.read_text())["projects"]


def test_an_unwritable_backup_aborts_before_mutating(tmp_path, monkeypatch):
    """AC-17. A prune that cannot be undone must not start."""
    home = tmp_path / "home"
    (home / ".config" / "set-core").mkdir(parents=True)
    registry = home / ".config" / "set-core" / "projects.json"
    original = json.dumps({"projects": {"gone": {"path": str(tmp_path / "gone")}}}, indent=2)
    registry.write_text(original)
    monkeypatch.setattr(project_registry, "PROJECTS_FILE", registry)

    def boom(*a, **kw):
        raise OSError("read-only filesystem")

    # patched on project_registry, which is where the backup actually lives
    monkeypatch.setattr(project_registry.shutil, "copy2", boom)

    with pytest.raises(OSError):
        rp.run_prune(preview=False)

    assert registry.read_text() == original


# ─── Threshold parsing ────────────────────────────────────────────────


@pytest.mark.parametrize("spec,days", [("30d", 30), ("30", 30), ("0d", 0), (" 7D ", 7)])
def test_parse_days_accepts(spec, days):
    assert rp._parse_days(spec) == days


@pytest.mark.parametrize("spec", ["", "soon", "30days", "-5", "1w", "d"])
def test_parse_days_rejects(spec):
    with pytest.raises(ValueError):
        rp._parse_days(spec)
