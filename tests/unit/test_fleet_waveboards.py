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
