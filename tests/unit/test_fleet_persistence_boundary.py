"""Nothing derived from an agent's session is persisted — task 2.7.

**Driven rather than asserted about.** A test that read the source for `open(...)`
calls would be a substring check wearing a guarantee: it passes while a logger
formats a conversation into a line, and it fails on a docstring that mentions
writing. So this runs the fleet's read paths over a session log carrying a
distinctive marker, and then looks for that marker in the two places content can
escape to — the filesystem, and the log records.

The boundary is PERSISTENCE, not naming. `read_conversation` returning the
conversation is the whole point of it; the rule is that nothing writes it down.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from set_orch.fleet import layout as layout_mod
from set_orch.fleet import state as state_mod
from set_orch.fleet.conversation import read_conversation
from set_orch.fleet.state import read_state

#: Distinctive enough that a match cannot be a coincidence, and shaped like the
#: content this boundary exists for: a partner name in a business sentence.
MARKER = "ZZQX-partner-Kovacs-order-88213-confidential"


def _session_log(tmp_path: Path) -> str:
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(json.dumps(entry) for entry in [
        {"type": "user", "message": {"content": [{"type": "text", "text": MARKER}]}},
        {"type": "assistant", "timestamp": "2026-08-19T00:00:00.000Z",
         "message": {"content": [
             {"type": "text", "text": f"working on {MARKER}"},
             {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": MARKER}},
         ]}},
    ]) + "\n", encoding="utf-8")
    return str(path)


def _files_under(root: Path):
    for base, _dirs, names in os.walk(root):
        for name in names:
            yield Path(base) / name


def test_reading_a_session_writes_none_of_it_anywhere(tmp_path, caplog):
    """The read paths the surface uses, run over a marked log."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    log = _session_log(tmp_path)

    # A second log with no outstanding call, so the declared reason is not
    # contradicted — `waiting_for` is session-derived content and must be shown
    # to have reached the reader before its absence from disk means anything.
    quiet = tmp_path / "quiet.jsonl"
    quiet.write_text(json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}}
    ) + "\n", encoding="utf-8")

    with caplog.at_level(logging.DEBUG):
        state = read_state(log)
        waiting = read_state(str(quiet), record={"status": "waiting", "waitingFor": MARKER})
        conversation = read_conversation(log, limit=50)
        layout_mod.save({"groups": [{"name": "g", "projects": ["p"]}]},
                        path=str(scratch / "fleet-layout.json"))

    # The content really did reach the caller — otherwise this test would pass by
    # reading nothing at all, which is the shape that proves nothing.
    assert any(MARKER in json.dumps(turn) for turn in conversation["turns"]), \
        "the fixture never reached the reader; this test would be vacuous"
    assert waiting.waiting_for == MARKER, "the reason really is session-derived content"
    assert state.state == "working"

    written = [p for p in _files_under(scratch)]
    assert written, "nothing was written at all; the check would be vacuous"
    for path in written:
        assert MARKER not in path.read_text(encoding="utf-8", errors="replace"), path
        assert MARKER not in str(path), "content reached a FILENAME"

    leaked = [r.getMessage() for r in caplog.records if MARKER in r.getMessage()]
    assert leaked == [], f"session content reached the log: {leaked[:2]}"


def test_a_read_failure_names_the_file_and_the_kind_never_the_content(tmp_path, caplog):
    """The diagnostic path is where this boundary is usually crossed: an error
    handler that dumps the record to aid debugging. It may name the file and the
    failure kind — both are shape — and nothing else.
    """
    log = _session_log(tmp_path)
    os.chmod(log, 0o000)
    try:
        with caplog.at_level(logging.DEBUG):
            state = read_state(log)
            conversation = read_conversation(log, limit=5)
    finally:
        os.chmod(log, 0o644)

    if os.geteuid() == 0:                     # root ignores the mode; nothing to test
        pytest.skip("running as root, the permission cannot be made to fail")

    assert state.state == "unknown" and state.reason
    assert conversation.get("problem")
    for record in caplog.records:
        assert MARKER not in record.getMessage()


def test_the_marker_would_have_been_found_if_it_had_leaked(tmp_path, caplog):
    """Proves the detector fires. A check that reports clean is indistinguishable
    from one that cannot report anything, and this file's whole value is its
    zeroes.
    """
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "leak.txt").write_text(f"prefix {MARKER} suffix", encoding="utf-8")
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("set_orch.fleet.test").warning("leaking %s", MARKER)

    found_on_disk = [p for p in _files_under(scratch) if MARKER in p.read_text()]
    found_in_log = [r for r in caplog.records if MARKER in r.getMessage()]
    assert found_on_disk and found_in_log, "the detector cannot see a leak it was shown"
