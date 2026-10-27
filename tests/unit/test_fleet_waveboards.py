"""The fleet's wave-board summaries — `set_orch.fleet.waveboards`.

Written against the RESULT payload: what a reader of the header would be told.
Job files are real files under tmp_path, because the directory layout
(`docs/waveboard/<job>.json`) is the mechanism being read.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from set_orch.fleet.waveboards import read_waveboards, summarise_board


def _item(i, status, updated="2026-10-01T10:00:00Z", title="secret item title", note="secret note"):
    return {"id": i, "title": title, "status": status, "evidence": None,
            "note": note, "updated": updated, "by": "agent"}


def _job(job="j", waves=(), url="https://claude.ai/artifact/x"):
    return {"schema": "set-wave-board/1", "job": job, "title": f"Board {job}",
            "artifact_url": url, "created": "2026-10-01", "waves": list(waves)}


def _write(root, job, data):
    d = root / "docs" / "waveboard"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{job}.json"
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return p


def _project(root, name):
    return SimpleNamespace(root=str(root), name=name)


def test_counts_and_current_wave(tmp_path):
    """AC-1: w0 all done, w1 one doing + one todo → counts, and w1 is current."""
    _write(tmp_path, "rel", _job("rel", [
        {"id": "w0", "title": "First", "items": [_item("a", "done"), _item("b", "done")]},
        {"id": "w1", "title": "Second", "items": [
            _item("c", "doing", "2026-10-03T09:00:00Z"), _item("d", "todo")]},
        {"id": "w2", "title": "Third", "items": [_item("e", "todo")]},
    ]))
    [board] = read_waveboards([_project(tmp_path, "proj")])
    assert board["unreadable"] is False
    assert board["project"] == "proj"
    assert board["counts"] == {"todo": 2, "doing": 1, "done": 2, "blocked": 0, "skipped": 0}
    assert board["current_wave"] == {"id": "w1", "title": "Second"}
    assert board["waves"] == 3
    assert board["updated"] == "2026-10-03T09:00:00Z"
    assert board["artifact_url"] == "https://claude.ai/artifact/x"


def test_skipped_does_not_hold_a_wave_open(tmp_path):
    """A wave of done + skipped is finished; the current wave is the next one."""
    _write(tmp_path, "j", _job("j", [
        {"id": "w0", "items": [_item("a", "done"), _item("b", "skipped")]},
        {"id": "w1", "items": [_item("c", "blocked")]},
    ]))
    [board] = read_waveboards([_project(tmp_path, "p")])
    assert board["current_wave"]["id"] == "w1"
    assert board["counts"]["blocked"] == 1


def test_finished_board_has_no_current_wave(tmp_path):
    """AC-2."""
    _write(tmp_path, "j", _job("j", [{"id": "w0", "items": [_item("a", "done"), _item("b", "skipped")]}]))
    [board] = read_waveboards([_project(tmp_path, "p")])
    assert board["current_wave"] is None


def test_project_without_boards_contributes_nothing(tmp_path):
    """AC-3."""
    assert read_waveboards([_project(tmp_path, "empty")]) == []


def test_malformed_file_is_an_entry_beside_a_good_one(tmp_path):
    """AC-4: the bad board is reported, and it hides nothing else."""
    bad, good = tmp_path / "bad", tmp_path / "good"
    _write(bad, "broken", "{not json")
    _write(good, "fine", _job("fine", [{"id": "w0", "items": [_item("a", "todo")]}]))
    boards = read_waveboards([_project(bad, "bad"), _project(good, "good")])
    assert len(boards) == 2
    broken = next(b for b in boards if b["project"] == "bad")
    assert broken["unreadable"] is True
    assert broken["job"] == "broken"
    assert "JSON" in broken["reason"]
    fine = next(b for b in boards if b["project"] == "good")
    assert fine["unreadable"] is False and fine["counts"]["todo"] == 1


def test_wrong_schema_is_unreadable(tmp_path):
    data = _job("j")
    data["schema"] = "something-else/2"
    _write(tmp_path, "j", data)
    [board] = read_waveboards([_project(tmp_path, "p")])
    assert board["unreadable"] is True
    assert "something-else/2" in board["reason"]


def test_item_content_never_leaves(tmp_path):
    """Summaries only: no item title, no note — the board page holds those."""
    _write(tmp_path, "j", _job("j", [{"id": "w0", "items": [_item("a", "doing")]}]))
    payload = json.dumps(read_waveboards([_project(tmp_path, "p")]))
    assert "secret item title" not in payload
    assert "secret note" not in payload


def test_unknown_status_is_counted_not_dropped(tmp_path):
    _write(tmp_path, "j", _job("j", [{"id": "w0", "items": [_item("a", "paused"), _item("b", "done")]}]))
    [board] = read_waveboards([_project(tmp_path, "p")])
    assert board["other"] == 1
    assert board["current_wave"]["id"] == "w0"


def test_non_https_url_is_not_offered_as_a_link(tmp_path):
    _write(tmp_path, "j", _job("j", url="javascript:alert(1)"))
    assert summarise_board("p", tmp_path / "docs" / "waveboard" / "j.json")["artifact_url"] is None


def test_same_root_twice_is_read_once(tmp_path):
    _write(tmp_path, "j", _job("j"))
    assert len(read_waveboards([_project(tmp_path, "a"), _project(tmp_path, "b")])) == 1


# ── staleness (change wave-board-staleness) ──────────────────────────────────
#
# A real git repository under tmp_path, with pinned commit dates: the count is
# the mechanism being read, so a fake would test a different thing.

import importlib.machinery
import importlib.util
import os
import subprocess
from pathlib import Path

from set_orch.fleet import waveboards as W

_REPO = Path(__file__).resolve().parents[2]
_GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def _commit(root, when, n=1):
    for i in range(n):
        stamp = f"{when}:{i:02d}Z"
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", f"c {stamp}"], cwd=root,
                       check=True, capture_output=True,
                       env={**os.environ, **_GIT_ENV, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})


def _git_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    _commit(root, "2025-12-01T00:00")
    return root


def _moved_past(tmp_path, commits=5, reviewed=None):
    root = _git_repo(tmp_path / "proj")
    job = _job("j", [{"id": "w0", "items": [
        _item("a", "todo", "2026-01-01T00:00:00Z"),
        dict(_item("b", "doing", "2026-01-01T00:00:00Z"), evidence={"type": "path-exists", "path": "x"}),
    ]}])
    if reviewed:
        job["reviewed"] = {"at": reviewed, "by": "host"}
    _write(root, "j", job)
    _commit(root, "2026-01-02T12:00", commits)
    return root


def test_a_board_the_repository_moved_past(tmp_path):
    """AC-13: one item sync cannot move, five newer commits."""
    root = _moved_past(tmp_path)
    [board] = read_waveboards([_project(root, "p")])
    assert board["manual_open"] == 1
    assert board["commits_since_change"] == 5
    assert board["stale"] is True
    assert board["reviewed"] is None


def test_a_reviewed_board_is_current(tmp_path):
    """AC-14."""
    root = _moved_past(tmp_path, reviewed="2026-01-03T00:00:00Z")
    [board] = read_waveboards([_project(root, "p")])
    assert board["commits_since_change"] == 0 and board["stale"] is False
    assert board["reviewed"] == "2026-01-03T00:00:00Z"


def test_a_project_without_git_is_null_not_zero(tmp_path):
    """AC-15."""
    _write(tmp_path, "j", _job("j", [{"id": "w0", "items": [_item("a", "todo")]}]))
    [board] = read_waveboards([_project(tmp_path, "p")])
    assert board["manual_open"] == 1
    assert board["commits_since_change"] is None and board["stale"] is False


def test_staleness_still_carries_no_item_title(tmp_path):
    root = _moved_past(tmp_path)
    payload = json.dumps(read_waveboards([_project(root, "p")]))
    assert "secret item title" not in payload and "secret note" not in payload


def _tool():
    loader = importlib.machinery.SourceFileLoader("set_wave_board_tool", str(_REPO / "bin" / "set-wave-board"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_the_tool_and_the_fleet_agree(tmp_path):
    """D9: the rule is written twice; both must give the same answer on one repository."""
    tool = _tool()
    assert tool.DEFAULT_STALE_COMMITS == W.DEFAULT_STALE_COMMITS
    root = _git_repo(tmp_path / "proj")
    job = _job("j", [{"id": "w0", "items": [
        _item("todo-none", "todo", "2026-01-01T00:00:00Z"),
        dict(_item("blocked-ev", "blocked", "2026-01-01T00:00:00Z"), evidence={"type": "path-exists", "path": "x"}),
        dict(_item("doing-ev", "doing", "2026-01-01T00:00:00Z"), evidence={"type": "path-exists", "path": "x"}),
        _item("done-none", "done", "2026-01-01T00:00:00Z"),
        _item("skipped-none", "skipped", "2026-01-01T00:00:00Z"),
    ]}])
    path = _write(root, "j", job)

    def both(data):
        path.write_text(json.dumps(data))
        cli, fleet = tool.staleness(root, "j", data), summarise_board("p", path)
        assert len(cli["manual_open"]) == fleet["manual_open"] == 2  # todo-none, blocked-ev
        assert cli["commits_since_change"] == fleet["commits_since_change"]
        assert cli["stale"] == fleet["stale"]
        return fleet["commits_since_change"], fleet["stale"]

    _commit(root, "2026-01-02T12:00", 2)
    assert both(job) == (2, False)
    _commit(root, "2026-01-03T12:00", 1)
    assert both(job) == (3, True)
    assert both(dict(job, reviewed={"at": "2026-01-05T00:00:00Z", "by": "h"})) == (0, False)


def test_without_any_stamp_the_created_date_counts(tmp_path):
    """D2: no item `updated`, no `reviewed` — the job's `created` date is the last change."""
    root = _git_repo(tmp_path / "proj")
    item = _item("a", "todo")
    del item["updated"]
    _write(root, "j", dict(_job("j", [{"id": "w0", "items": [item]}]), created="2026-01-01"))
    _commit(root, "2026-01-02T12:00", 3)
    [board] = read_waveboards([_project(root, "p")])
    assert board["commits_since_change"] == 3 and board["stale"] is True
