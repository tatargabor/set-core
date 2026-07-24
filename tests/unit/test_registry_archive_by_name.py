"""Archiving named entries — the operator-directed path, and where it differs
from the bulk one.

The bulk path refuses an entry with open issues so that a threshold cannot hide a
failure nobody looked at. Naming an entry is the looking. The two refusal sets are
therefore deliberately different, and the difference is what these tests pin: a
suite that refused both would kill the feature, and one that allowed both would
let the dashboard lie about running work.
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
    """One ordinary project, one E2E-style run, one recent run, one dead entry."""
    registry = tmp_path / "projects.json"
    e2e_root = tmp_path / "e2e-runs"
    plain = tmp_path / "plain-project"
    old_run = e2e_root / "old-run"
    new_run = e2e_root / "new-run"
    for d in (plain, old_run, new_run):
        d.mkdir(parents=True)
    ancient = time.time() - 200 * 86400
    os.utime(old_run, (ancient, ancient))
    os.utime(plain, (ancient, ancient))

    registry.write_text(json.dumps({
        "projects": {
            "plain": {"path": str(plain), "addedAt": "2026-01-01", "project_type": "web"},
            "old-run": {"path": str(old_run), "addedAt": "2026-01-01"},
            "new-run": {"path": str(new_run), "addedAt": "2026-01-01"},
            "dead": {"path": str(tmp_path / "gone"), "addedAt": "2026-01-01"},
        },
        "default": "plain",
    }, indent=2))
    monkeypatch.setattr(project_registry, "PROJECTS_FILE", registry)
    monkeypatch.setattr(rp, "e2e_runs_root", lambda: e2e_root)
    return {"registry": registry, "plain": plain, "old": old_run, "new": new_run}


def _entries(registry: Path) -> dict:
    return json.loads(registry.read_text())["projects"]


def _write_issues(project: Path, payload) -> None:
    issues = project / ".set" / "issues"
    issues.mkdir(parents=True, exist_ok=True)
    (issues / "registry.json").write_text(
        payload if isinstance(payload, str) else json.dumps(payload))
    ancient = time.time() - 200 * 86400
    os.utime(project, (ancient, ancient))


# ─── No age or location constraint on the named path ──────────────────


def test_a_project_outside_the_e2e_root_can_be_archived_by_name(reg):
    """AC-1. The E2E-root rule exists to stop AGE-based bulk selection from
    catching a real project. A name involves no selection, so it does not apply."""
    report = rp.archive_by_name(["plain"])
    assert report.archived == ["plain"]
    assert _entries(reg["registry"])["plain"]["archived"] is True


def test_a_recent_entry_can_be_archived_by_name(reg):
    """AC-2."""
    report = rp.archive_by_name(["new-run"])
    assert report.archived == ["new-run"]


# ─── The split that is the whole design ───────────────────────────────


def test_open_issues_warn_but_do_not_block_the_named_path(reg):
    """AC-3. The issues stay counted elsewhere; naming the project is the
    operator's decision that it no longer needs a row."""
    _write_issues(reg["old"], {"issues": [{"id": "ISS-1", "state": "failed"}]})
    report = rp.archive_by_name(["old-run"])
    assert report.archived == ["old-run"]
    assert report.refused == []
    assert any("1 open issue" in w for w in report.warnings), report.warnings


def test_the_bulk_path_still_refuses_the_same_entry(reg):
    """AC-4. Adding the named path must not weaken the threshold path — this is
    the same fixture entry the previous test archived."""
    _write_issues(reg["old"], {"issues": [{"id": "ISS-1", "state": "failed"}]})
    report = rp.run_prune(preview=False, archive_older_than="30d")
    assert report.archived == []
    assert [r.name for r in report.archive_refused] == ["old-run"]


def test_a_live_process_refuses_on_the_named_path_too(reg, monkeypatch):
    """AC-5. Present state, not past information: hiding a project that is
    running makes the dashboard wrong about the machine. No override exists."""
    monkeypatch.setattr(rp, "_live_process", lambda p: "orchestrator" if p == reg["old"] else None)
    report = rp.archive_by_name(["old-run"])
    assert report.archived == []
    assert "orchestrator is running" in report.refused[0].reason
    assert "archived" not in _entries(reg["registry"])["old-run"]


def test_a_missing_directory_refuses_and_names_the_other_command(reg):
    """AC-6. A dead entry hidden behind a flag is the worst of both — it belongs
    to deregistration."""
    report = rp.archive_by_name(["dead"])
    assert report.archived == []
    assert "set-project prune" in report.refused[0].reason


def test_there_is_no_flag_that_overrides_a_refusal():
    """The refusals are not configurable — asserted on the signature, so adding a
    `force` parameter has to be a deliberate spec change, not a quiet default."""
    import inspect
    params = set(inspect.signature(rp.archive_by_name).parameters)
    assert params == {"names", "undo", "preview", "registry_file"}, params


# ─── Atomicity ────────────────────────────────────────────────────────


def test_an_unknown_name_aborts_before_any_write(reg):
    """AC-7. Partial application is the shape where an operator believes the whole
    command worked: the error is one line up the scrollback, the state is half
    changed."""
    before = reg["registry"].read_bytes()
    report = rp.archive_by_name(["plain", "typo-name", "new-run"])
    assert report.unknown == ["typo-name"]
    assert report.archived == []
    assert reg["registry"].read_bytes() == before
    assert list(reg["registry"].parent.glob("*.bak-*")) == []


# ─── The way back ─────────────────────────────────────────────────────


def test_archive_then_unarchive_round_trips(reg):
    """AC-8."""
    before = dict(_entries(reg["registry"])["plain"])
    rp.archive_by_name(["plain"])
    assert _entries(reg["registry"])["plain"]["archived"] is True
    report = rp.archive_by_name(["plain"], undo=True)
    assert report.unarchived == ["plain"]
    assert _entries(reg["registry"])["plain"] == before


def test_unarchiving_a_plain_entry_is_a_reported_noop(reg):
    """AC-9. Silence would leave the operator unsure whether it worked."""
    before = reg["registry"].read_bytes()
    report = rp.archive_by_name(["new-run"], undo=True)
    assert report.noop == ["new-run"]
    assert report.unarchived == []
    assert reg["registry"].read_bytes() == before


def test_archiving_an_already_archived_entry_is_a_reported_noop(reg):
    rp.archive_by_name(["new-run"])
    report = rp.archive_by_name(["new-run"])
    assert report.noop == ["new-run"]
    assert report.archived == []


# ─── The default pointer ──────────────────────────────────────────────


def test_archiving_the_default_clears_it_and_reports_it(reg):
    """AC-10. An archived default is absent from every list yet still default —
    a pointer that looks configured and behaves as if nothing is set."""
    report = rp.archive_by_name(["plain"])
    assert report.default_cleared == "plain"
    assert json.loads(reg["registry"].read_text())["default"] is None
    assert "cleared the default" in rp.format_name_report(report)


def test_archiving_a_non_default_leaves_the_default_alone(reg):
    """The clearing must discriminate, or it silently unsets a working default."""
    report = rp.archive_by_name(["old-run"])
    assert report.default_cleared is None
    assert json.loads(reg["registry"].read_text())["default"] == "plain"


# ─── Preview and backup ───────────────────────────────────────────────


def test_preview_writes_nothing(reg):
    """AC-11."""
    before_bytes = reg["registry"].read_bytes()
    before_mtime = reg["registry"].stat().st_mtime_ns
    time.sleep(0.01)
    report = rp.archive_by_name(["plain"], preview=True)
    assert report.archived == ["plain"]          # it did decide
    assert reg["registry"].read_bytes() == before_bytes
    assert reg["registry"].stat().st_mtime_ns == before_mtime
    assert list(reg["registry"].parent.glob("*.bak-*")) == []
    assert report.backup_path is None


def test_backup_precedes_mutation(reg):
    """AC-12."""
    original = reg["registry"].read_text()
    report = rp.archive_by_name(["plain"])
    backups = list(reg["registry"].parent.glob("projects.json.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == original
    assert report.backup_path == str(backups[0])


def test_nothing_on_disk_is_touched(reg):
    """Archiving is a registry flag. The project's own files are not its business."""
    marker = reg["plain"] / "keep.txt"
    marker.write_text("content")
    rp.archive_by_name(["plain"])
    assert marker.read_text() == "content"
    assert reg["plain"].is_dir()
