"""The check to run after an actual reboot.

Its output is read by a person deciding whether their work survived, so the
properties under test are about what it REFUSES to claim: it must not print a
zero it did not measure, and it must not report a roster that does not exist as
an empty one.
"""

from __future__ import annotations

import json
import os

import pytest

from set_orch.fleet import discovery, roster, roster_cli


class _A:
    def __init__(self, cwd, session_id, name):
        self.pid, self.cwd, self.session_id = 1, cwd, session_id
        self.name, self.project_name, self.kind = name, os.path.basename(cwd), "interactive"


def _seed(tmp_path, sessions, with_logs=True):
    cwd = tmp_path / "proj"; cwd.mkdir(exist_ok=True)
    path = str(tmp_path / "store" / "fleet-roster.json")
    roster.record([_A(str(cwd), s, f"proj-{s.lower()}") for s in sessions], path=path, now=1000.0)
    if with_logs:
        d = tmp_path / "projects" / "-proj"; d.mkdir(parents=True, exist_ok=True)
        for s in sessions:
            (d / f"{s}.jsonl").write_text("{}\n")
    return path


def test_a_missing_roster_is_reported_as_missing_not_as_empty(tmp_path, capsys):
    """"Nothing has been recorded" and "the record is empty" lead to different
    actions, and the exit code separates them from success.
    """
    code = roster_cli.main(["--path", str(tmp_path / "nope.json"), "verify"])
    out = capsys.readouterr().out
    assert code == 1
    assert "no roster at" in out
    assert "first one AFTER" in out, "it must say when the feature starts covering a reboot"


def test_unmeasurable_liveness_is_printed_as_unknown_never_as_zero(tmp_path, monkeypatch, capsys):
    """A gap is not a zero. "0 already running" is the number a reader acts on,
    and printing it unmeasured would be a claim nobody made.
    """
    path = _seed(tmp_path, ["S1", "S2"])
    monkeypatch.setattr(discovery, "SESSION_LOG_ROOT", tmp_path / "projects")
    monkeypatch.setattr(discovery, "live_session_ids", lambda: None)
    roster_cli.main(["--path", path, "verify"])
    out = capsys.readouterr().out
    assert "unknown how many" in out
    assert "unmeasured, not zero" in out
    assert "0 already running" not in out


def test_the_reboot_shape_is_what_it_prints(tmp_path, monkeypatch, capsys):
    """The state after a boot: everything recorded, everything resumable,
    nothing running. This is the line the user reads to know it worked.
    """
    path = _seed(tmp_path, ["S1", "S2", "S3"])
    monkeypatch.setattr(discovery, "SESSION_LOG_ROOT", tmp_path / "projects")
    monkeypatch.setattr(discovery, "live_session_ids", lambda: set())
    assert roster_cli.main(["--path", path, "verify"]) == 0
    assert "3 entries, 3 resumable now, 0 already running" in capsys.readouterr().out


def test_an_entry_with_no_transcript_is_counted_out_and_explained(tmp_path, monkeypatch, capsys):
    path = _seed(tmp_path, ["S1", "S2"], with_logs=False)
    monkeypatch.setattr(discovery, "SESSION_LOG_ROOT", tmp_path / "projects")
    monkeypatch.setattr(discovery, "live_session_ids", lambda: set())
    roster_cli.main(["--path", path, "verify"])
    out = capsys.readouterr().out
    assert "2 entries, 0 resumable now" in out
    assert "kept and shown, not dropped" in out


def test_json_output_carries_whether_liveness_was_known(tmp_path, monkeypatch, capsys):
    """A machine reader needs the same distinction the human one gets."""
    path = _seed(tmp_path, ["S1"])
    monkeypatch.setattr(discovery, "SESSION_LOG_ROOT", tmp_path / "projects")
    monkeypatch.setattr(discovery, "live_session_ids", lambda: None)
    roster_cli.main(["--path", path, "verify", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["liveness_known"] is False
    assert payload["total"] == 1


def test_verify_is_the_default_subcommand(tmp_path, monkeypatch, capsys):
    """Someone typing `set-fleet-roster` after a reboot wants the answer, not a
    usage message.
    """
    path = _seed(tmp_path, ["S1"])
    monkeypatch.setattr(discovery, "SESSION_LOG_ROOT", tmp_path / "projects")
    monkeypatch.setattr(discovery, "live_session_ids", lambda: set())
    assert roster_cli.main(["--path", path]) == 0
    assert "1 entries, 1 resumable now" in capsys.readouterr().out
