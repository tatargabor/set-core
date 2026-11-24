"""B-214: Enter typed in the asking agent's terminal hands a relay-held question back there.

Measured 2026-11-24: a relayed AskUserQuestion holds the turn inside the hook, a message the
operator typed only queued behind it, and the agent sat for 16 min. The fleet's terminal now
releases on Enter, as "answer here instead" does.
"""
from __future__ import annotations

import json
import os

from set_orch.fleet import question_relay as qr

SID = "a5bc0d35-104b-42a2-9f3f-0d97cf111903"
PID = 2938953


def world(tmp_path, kind=None):
    records = tmp_path / "sessions"
    records.mkdir()
    (records / f"{PID}.json").write_text(json.dumps({"pid": PID, "sessionId": SID}))
    base = tmp_path / "state"
    rec = {"session_id": SID, "id": "relay-a5bc0d35-1", "questions": 1, "pid": os.getpid()}
    if kind:
        rec["kind"] = kind
    qr._write_json(qr.waiting_path(SID, base), rec)
    return base, records


def test_enter_releases_a_held_question(tmp_path):
    base, records = world(tmp_path)
    assert qr.release_on_terminal_enter(PID, base, records) == SID
    assert qr.release_path(SID, base).exists()
    # a second Enter does not re-request
    assert qr.release_on_terminal_enter(PID, base, records) is None


def test_a_permission_prompt_is_handed_back_too(tmp_path):
    base, records = world(tmp_path, kind="permission")
    assert qr.release_on_terminal_enter(PID, base, records) == SID


def test_a_continuation_is_left_to_the_typed_prompt(tmp_path):
    base, records = world(tmp_path, kind="continuation")
    assert qr.release_on_terminal_enter(PID, base, records) is None
    assert not qr.release_path(SID, base).exists()


def test_nothing_waiting_or_no_session_record_is_a_no_op(tmp_path):
    base, records = world(tmp_path)
    qr.waiting_path(SID, base).unlink()
    assert qr.release_on_terminal_enter(PID, base, records) is None
    assert qr.release_on_terminal_enter(12345, base, records) is None


def test_project_name_falls_back_to_the_repo_root_not_the_current_directory(tmp_path, monkeypatch):
    """Measured 2026-11-24: a Stop hook in <repo>/lib was labelled 'lib' when the git lookup
    raised. The fallback now walks up to the directory holding .git."""
    import set_orch.paths as paths
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)
    (repo / "lib" / "deep").mkdir(parents=True)
    def boom(_cwd):
        raise OSError("git not reachable")
    monkeypatch.setattr(paths, "resolve_project_name", boom)
    assert qr._project_name(str(repo / "lib" / "deep")) == "myrepo"
    assert qr._project_name(str(tmp_path / "nowhere")) == "nowhere"
