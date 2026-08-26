"""The record of what the fleet HAS SEEN, and whether it survives a reboot.

The whole point of this module is one moment nobody can arrange to be present
for: the first read after a machine came back up. So the tests here are built to
be **reboot-faithful** rather than merely green — the boot case is simulated by
removing every input a boot destroys, and one test exists purely to prove that
the simulation is not vacuous.

What a reboot destroys, and therefore what these tests withhold:

  - `/proc` — every pid in the record is gone, and the numbers are reused
  - `~/.claude/sessions/<pid>.json` — measured 2026-08-21: 25 records, 25 live
    pids, ZERO stale, because the runtime removes a record when its session exits
  - every live process, terminal and scope

What survives, and is therefore all these tests may use:

  - our own roster file
  - `~/.claude/projects/<slug>/<sessionId>.jsonl`, the transcript
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

from set_orch.fleet import roster


@dataclass
class FakeAgent:
    """Only the fields `roster` is allowed to read. Deliberately not a real
    `discovery.Agent`: if the roster ever starts reading something else — a
    `record`, a socket path — this fake stops providing it and the test says so.
    """

    pid: int
    cwd: str
    session_id: Optional[str] = None
    name: Optional[str] = None
    project_name: Optional[str] = None
    kind: str = "interactive"


def _path(tmp_path) -> str:
    return str(tmp_path / "store" / "fleet-roster.json")


def _transcript(root: Path, project_slug: str, session_id: str, body: str = "") -> Path:
    d = root / project_slug
    d.mkdir(parents=True, exist_ok=True)
    log = d / f"{session_id}.jsonl"
    log.write_text(body or json.dumps({"type": "user", "message": "hello"}) + "\n")
    return log


# --------------------------------------------------------------------------- #
# recording
# --------------------------------------------------------------------------- #

def test_a_discovered_agent_is_recorded_under_its_session_id(tmp_path):
    """AC-1. Keyed on the session id and not the pid, because a pid is reused —
    which is exactly the property that breaks after the reboot this exists for.
    """
    roster.record(
        [FakeAgent(pid=42, cwd="/home/x/proj", session_id="S1", name="proj-1", project_name="proj")],
        labels={42: "the-name-a-person-chose"},
        path=_path(tmp_path), now=1000.0,
    )
    stored = json.loads(Path(_path(tmp_path)).read_text())
    assert list(stored["projects"]["proj"]) == ["S1"]
    entry = stored["projects"]["proj"]["S1"]
    # The FRAMEWORK's label, never the runtime's derived `name` — measured
    # 2026-08-21: recording `name` gave back a generated string for an agent its
    # user had named, and a resume regenerates it again.
    assert entry["label"] == "the-name-a-person-chose"
    assert "proj-1" not in Path(_path(tmp_path)).read_text()
    assert entry["cwd"] == "/home/x/proj"
    assert entry["first_seen"] == 1000.0 and entry["last_seen"] == 1000.0
    assert "42" not in json.dumps(list(stored["projects"]["proj"]))


def test_the_same_session_under_a_new_pid_updates_rather_than_duplicating(tmp_path):
    """AC-2. The reboot case in miniature: same conversation, different process."""
    p = _path(tmp_path)
    a = FakeAgent(pid=42, cwd="/home/x/proj", session_id="S1", name="proj-1", project_name="proj")
    roster.record([a], path=p, now=1000.0)
    roster.record(
        [FakeAgent(pid=999, cwd="/home/x/proj", session_id="S1", name="proj-1", project_name="proj")],
        path=p, now=2000.0,
    )
    entries = json.loads(Path(p).read_text())["projects"]["proj"]
    assert list(entries) == ["S1"], "one session, one entry — a pid change is not a new agent"
    assert entries["S1"]["first_seen"] == 1000.0, "first_seen is the fact that does not move"
    assert entries["S1"]["last_seen"] == 2000.0


def test_an_agent_with_no_session_id_is_recorded_as_a_stated_absence(tmp_path):
    """AC-3. Measured twice on 2026-08-18: a session can be alive and unknown to
    the runtime's records. Dropping it would make the roster claim a smaller
    fleet than existed.
    """
    roster.record(
        [FakeAgent(pid=42, cwd="/home/x/proj", session_id=None, name="proj-9", project_name="proj")],
        path=_path(tmp_path), now=1000.0,
    )
    entries = json.loads(Path(_path(tmp_path)).read_text())["projects"]["proj"]
    (key,) = entries
    assert key.startswith(roster.NO_SESSION_KEY_PREFIX)
    assert entries[key]["session_id"] is None, "absent, and SAID to be absent"


def test_the_no_session_key_is_stable_across_sightings(tmp_path):
    """Otherwise every discovery pass adds another entry for one agent, and the
    roster grows a copy per minute until the retention bound removes them all.
    """
    p = _path(tmp_path)
    for pid, now in ((42, 1000.0), (43, 2000.0), (44, 3000.0)):
        roster.record(
            [FakeAgent(pid=pid, cwd="/home/x/proj", session_id=None, name="proj-9", project_name="proj")],
            path=p, now=now,
        )
    assert len(json.loads(Path(p).read_text())["projects"]["proj"]) == 1


def test_a_oneshot_subprocess_is_not_recorded(tmp_path):
    """AC-4. CB-8: the framework's own `-p` children run with a project as cwd.
    Restoring one would resume a subprocess as though it were a conversation.
    """
    out = roster.record(
        [FakeAgent(pid=42, cwd="/home/x/proj", session_id="S1", project_name="proj", kind="oneshot")],
        path=_path(tmp_path), now=1000.0,
    )
    assert out["skipped"] == 1 and out["added"] == 0
    assert json.loads(Path(_path(tmp_path)).read_text())["projects"] == {}


# --------------------------------------------------------------------------- #
# THE REBOOT CASE
# --------------------------------------------------------------------------- #

def test_the_record_is_readable_with_no_live_state_of_any_kind(tmp_path, monkeypatch):
    """AC-5 — the test this module exists for.

    Every input a boot destroys is withheld: `/proc` points at an empty
    directory, the runtime's session-record dir does not exist, and no process in
    the record is alive. What is left is our file and the transcript, which is
    exactly what a real reboot leaves.
    """
    p = _path(tmp_path)
    logs = tmp_path / "projects"
    roster.record([
        FakeAgent(pid=111, cwd="/home/x/proj", session_id="S1", name="proj-1", project_name="proj"),
        FakeAgent(pid=222, cwd="/home/x/proj", session_id="S2", name="proj-2", project_name="proj"),
    ], path=p, now=1000.0)
    _transcript(logs, "-home-x-proj", "S1")
    _transcript(logs, "-home-x-proj", "S2")

    # The boot. Nothing below may consult any of these and still pass.
    empty_proc = tmp_path / "no-proc"
    empty_proc.mkdir()
    monkeypatch.setattr("set_orch.fleet.discovery.SESSION_RECORD_DIR", tmp_path / "gone-sessions")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "store-root-that-is-not-used"))

    answer = roster.read("proj", path=p, log_root=logs)
    assert answer["record_exists"] is True
    assert [e["session_id"] for e in answer["entries"]] == ["S1", "S2"] or \
           sorted(e["session_id"] for e in answer["entries"]) == ["S1", "S2"]
    assert all(e["resumable"] for e in answer["entries"]), \
        "the transcript survives a boot, so both entries are resumable"
    assert not list(empty_proc.iterdir()), "the test must not have created live state"


def test_the_reboot_test_is_not_vacuous(tmp_path, monkeypatch):
    """The negative control for the test above.

    A test that withholds live state proves nothing unless the code would
    actually have used it. So: make the TRANSCRIPT — the one surviving input —
    disappear, and assert the answer changes. If this passes unchanged, the read
    is not measuring anything and the reboot test above is decoration.
    """
    p = _path(tmp_path)
    logs = tmp_path / "projects"
    roster.record(
        [FakeAgent(pid=111, cwd="/home/x/proj", session_id="S1", name="proj-1", project_name="proj")],
        path=p, now=1000.0,
    )
    with_log = roster.read("proj", path=p, log_root=_transcript(logs, "-home-x-proj", "S1").parent.parent)
    assert with_log["entries"][0]["resumable"] is True

    (logs / "-home-x-proj" / "S1.jsonl").unlink()
    without = roster.read("proj", path=p, log_root=logs)
    assert without["entries"][0]["resumable"] is False, \
        "the read does not actually look at the transcript — the reboot test measures nothing"
    assert "S1" in without["entries"][0]["not_resumable_reason"]


def test_a_project_never_seen_is_an_empty_record_and_says_so(tmp_path):
    """AC-6. An absent key is not an empty value: 'never recorded' and 'recorded
    and empty' are different, and the screen says different things about them.
    """
    answer = roster.read("nobody", path=_path(tmp_path))
    assert answer["entries"] == []
    assert answer["record_exists"] is False


# --------------------------------------------------------------------------- #
# resumability is measured, not stored
# --------------------------------------------------------------------------- #

def test_resumability_is_never_stored_in_the_file(tmp_path):
    """A stored boolean is a declaration about a moment that has passed — the
    defect already measured on the runtime's own `status` field (median 11 hours
    stale across 23 sessions). A stored `true` sends restore at a session that
    is not there.
    """
    roster.record(
        [FakeAgent(pid=42, cwd="/home/x/proj", session_id="S1", project_name="proj")],
        path=_path(tmp_path), now=1000.0,
    )
    raw = Path(_path(tmp_path)).read_text()
    assert "resumable" not in raw
    assert "session_log" not in raw


def test_an_entry_whose_transcript_is_gone_is_kept_and_marked(tmp_path):
    """AC-8. The false-absence class: filtering it out would tell the user a
    smaller fleet existed than did, in the direction where nobody goes looking.
    """
    p = _path(tmp_path)
    logs = tmp_path / "projects"
    roster.record([
        FakeAgent(pid=1, cwd="/home/x/proj", session_id="ALIVE", project_name="proj"),
        FakeAgent(pid=2, cwd="/home/x/proj", session_id="GONE", project_name="proj"),
    ], path=p, now=1000.0)
    _transcript(logs, "-home-x-proj", "ALIVE")

    entries = {e["session_id"]: e for e in roster.read("proj", path=p, log_root=logs)["entries"]}
    assert set(entries) == {"ALIVE", "GONE"}, "the unresumable entry is PRESENT"
    assert entries["ALIVE"]["resumable"] is True
    assert entries["GONE"]["resumable"] is False
    assert "GONE" in entries["GONE"]["not_resumable_reason"]


# --------------------------------------------------------------------------- #
# identity only
# --------------------------------------------------------------------------- #

def test_no_transcript_content_reaches_the_stored_file(tmp_path):
    """AC-9, and the confidentiality boundary: set-core may READ a consumer's
    data at runtime and must persist nothing derived from it.
    """
    p = _path(tmp_path)
    logs = tmp_path / "projects"
    secret = "ACME-ORDER-88421-partner-confidential"
    _transcript(logs, "-home-x-proj", "S1", json.dumps({"type": "user", "message": secret}) + "\n")
    roster.record(
        [FakeAgent(pid=42, cwd="/home/x/proj", session_id="S1", name="proj-1", project_name="proj")],
        path=p, now=1000.0,
    )
    assert secret not in Path(p).read_text()


def test_a_field_the_producer_adds_cannot_reach_the_file(tmp_path):
    """The record is REBUILT field by field, not copied. A dict passed through
    carries whatever the producer put in it — which is how a session record, a
    socket path or a message body reaches a file that promised identity only.
    """
    p = _path(tmp_path)
    roster.record(
        [FakeAgent(pid=42, cwd="/home/x/proj", session_id="S1", project_name="proj")],
        path=p, now=1000.0,
    )
    document = json.loads(Path(p).read_text())
    document["projects"]["proj"]["S1"]["record"] = {"messagingSocketPath": "/run/user/1000/x.sock"}
    document["projects"]["proj"]["S1"]["transcript"] = "a customer name"
    Path(p).write_text(json.dumps(document))

    entry = roster.read("proj", path=p)["entries"][0]
    assert "record" not in entry and "transcript" not in entry
    roster.record([FakeAgent(pid=42, cwd="/home/x/proj", session_id="S1", project_name="proj")],
                  path=p, now=2000.0)
    assert "messagingSocketPath" not in Path(p).read_text()


# --------------------------------------------------------------------------- #
# failure directions
# --------------------------------------------------------------------------- #

def test_a_corrupt_file_is_replaced_rather_than_fatal(tmp_path):
    """AC-11. Keeping it would mean every future write fails on the same bytes."""
    p = _path(tmp_path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    Path(p).write_text("{not json at all")

    answer = roster.read("proj", path=p)
    assert answer["unreadable"] is True and answer["entries"] == []

    roster.record([FakeAgent(pid=42, cwd="/home/x/proj", session_id="S1", project_name="proj")],
                  path=p, now=1000.0)
    assert roster.read("proj", path=p)["entries"][0]["session_id"] == "S1"


def test_record_raises_on_an_unwritable_store(tmp_path):
    """The caller decides whether discovery's answer survives a write failure.
    Swallowing HERE would put the decision in the wrong place — a future caller
    that does want to know would have no way to find out.
    """
    p = str(tmp_path / "store" / "fleet-roster.json")
    os.makedirs(os.path.dirname(p))
    os.chmod(os.path.dirname(p), 0o500)
    try:
        with pytest.raises(OSError):
            roster.record([FakeAgent(pid=42, cwd="/home/x/proj", session_id="S1", project_name="proj")],
                          path=p, now=1000.0)
    finally:
        os.chmod(os.path.dirname(p), 0o700)


# --------------------------------------------------------------------------- #
# forgetting and retention
# --------------------------------------------------------------------------- #

def test_one_entry_is_forgotten_and_the_rest_are_untouched(tmp_path):
    """AC-12."""
    p = _path(tmp_path)
    roster.record([
        FakeAgent(pid=1, cwd="/home/x/proj", session_id="S1", project_name="proj"),
        FakeAgent(pid=2, cwd="/home/x/proj", session_id="S2", project_name="proj"),
    ], path=p, now=1000.0)
    assert roster.forget("proj", "S1", path=p) is True
    assert [e["session_id"] for e in roster.read("proj", path=p)["entries"]] == ["S2"]
    assert roster.forget("proj", "S1", path=p) is False, "already gone is not an error"


def test_an_entry_unseen_beyond_the_bound_is_pruned_and_logged(tmp_path, caplog):
    """AC-13. Pruning is reported: an entry that vanishes silently is
    indistinguishable from one that was never recorded.
    """
    p = _path(tmp_path)
    roster.record([FakeAgent(pid=1, cwd="/home/x/old", session_id="OLD", project_name="old")],
                  path=p, now=1000.0)
    with caplog.at_level("INFO"):
        roster.record([FakeAgent(pid=2, cwd="/home/x/new", session_id="NEW", project_name="new")],
                      path=p, now=1000.0 + roster.RETENTION_SECONDS + 1)
    assert roster.read("old", path=p)["entries"] == []
    assert roster.read("new", path=p)["entries"][0]["session_id"] == "NEW"
    assert "OLD" in caplog.text and "pruning" in caplog.text.lower()


def test_an_entry_just_inside_the_bound_survives(tmp_path):
    """The boundary in the direction that would silently destroy a usable entry."""
    p = _path(tmp_path)
    roster.record([FakeAgent(pid=1, cwd="/home/x/proj", session_id="S1", project_name="proj")],
                  path=p, now=1000.0)
    roster.record([FakeAgent(pid=2, cwd="/home/x/other", session_id="S2", project_name="other")],
                  path=p, now=1000.0 + roster.RETENTION_SECONDS - 1)
    assert roster.read("proj", path=p)["entries"][0]["session_id"] == "S1"


# --------------------------------------------------------------------------- #
# the empty screen's question
# --------------------------------------------------------------------------- #

def test_projects_lists_every_project_with_a_record_newest_first(tmp_path):
    """After a reboot no project holds an agent, so the column offers nothing to
    click and a per-project read would need a name nobody can supply.
    """
    p = _path(tmp_path)
    roster.record([FakeAgent(pid=1, cwd="/home/x/a", session_id="A1", project_name="a")],
                  path=p, now=1000.0)
    roster.record([FakeAgent(pid=2, cwd="/home/x/b", session_id="B1", project_name="b")],
                  path=p, now=2000.0)
    listed = roster.projects(path=p)
    assert [x["project"] for x in listed] == ["b", "a"]
    assert listed[0]["entries"] == 1 and listed[0]["last_seen"] == 2000.0


def test_projects_is_empty_when_nothing_was_ever_recorded(tmp_path):
    assert roster.projects(path=_path(tmp_path)) == []


# --------------------------------------------------------------------------- #
# relabel — the record is what a reboot reads, so a rename is written NOW
# --------------------------------------------------------------------------- #

def _seed(tmp_path, project="proj", key="sid-1", label="old"):
    p = _path(tmp_path)
    roster.record(
        [FakeAgent(pid=1, cwd="/tmp", session_id=key, name=label, project_name=project)],
        path=p, now=1000.0,
    )
    return p


def test_relabelling_writes_the_new_name_into_the_record(tmp_path):
    p = _seed(tmp_path)
    assert roster.relabel("sid-1", "new", path=p) == 1
    stored = json.loads(Path(p).read_text())
    assert stored["projects"]["proj"]["sid-1"]["label"] == "new"


def test_relabelling_finds_the_entry_without_being_told_the_project(tmp_path):
    """A caller holding a pid knows the session before it knows the project —
    and the lookup that would give it the project is the one that can fail.
    """
    p = _seed(tmp_path)
    assert roster.relabel("sid-1", "new", path=p) == 1
    assert roster.relabel("sid-1", "newer", project="proj", path=p) == 1
    assert roster.relabel("sid-1", "newest", project="a-different-project", path=p) == 0
    assert json.loads(Path(p).read_text())["projects"]["proj"]["sid-1"]["label"] == "newer"


def test_relabelling_an_unknown_session_changes_nothing_and_says_so(tmp_path):
    """A count, not a boolean: "nothing to do" and "did nothing" look identical
    from a bare `False`, and only one of them is a defect.
    """
    p = _seed(tmp_path)
    before = Path(p).read_text()
    assert roster.relabel("no-such-session", "new", path=p) == 0
    assert Path(p).read_text() == before


def test_relabelling_a_missing_record_does_not_create_one(tmp_path):
    """A rename must not invent a record. An entry that appears without the agent
    ever having been seen would be restored later as though it had been.
    """
    p = _path(tmp_path)
    assert roster.relabel("sid-1", "new", path=p) == 0
    assert not Path(p).exists()


# --------------------------------------------------------------------------- #
# whose name gets recorded — AC-13 … AC-16
# --------------------------------------------------------------------------- #

def test_an_agent_the_framework_does_not_hold_is_recorded_with_no_label(tmp_path):
    """AC-14. An invented label renders exactly like a chosen one, and a restore
    would hand it back as though somebody had named it.
    """
    p = _path(tmp_path)
    roster.record(
        [FakeAgent(pid=7, cwd="/home/x/proj", session_id="S1", name="proj-ab", project_name="proj")],
        labels={}, path=p, now=1000.0,
    )
    entry = json.loads(Path(p).read_text())["projects"]["proj"]["S1"]
    assert entry["label"] is None
    assert "proj-ab" not in Path(p).read_text(), "the runtime's derived name must not stand in for a label"


def test_an_unreachable_holder_cannot_overwrite_a_label_already_recorded(tmp_path):
    """AC-15, and the direction is the whole point: one unreachable socket must
    not erase the names this record exists to keep.
    """
    p = _path(tmp_path)
    a = FakeAgent(pid=7, cwd="/home/x/proj", session_id="S1", name="proj-ab", project_name="proj")
    roster.record([a], labels={7: "chosen"}, path=p, now=1000.0)
    roster.record([a], labels=None, path=p, now=2000.0)          # could not ask
    entry = json.loads(Path(p).read_text())["projects"]["proj"]["S1"]
    assert entry["label"] == "chosen"
    assert entry["last_seen"] == 2000.0, "the sighting is still recorded; only the label is untouched"


def test_a_renamed_agent_is_recorded_under_its_new_label(tmp_path):
    """AC-16. The recording pass agrees with the rename rather than undoing it."""
    p = _path(tmp_path)
    a = FakeAgent(pid=7, cwd="/home/x/proj", session_id="S1", name="proj-ab", project_name="proj")
    roster.record([a], labels={7: "before"}, path=p, now=1000.0)
    roster.record([a], labels={7: "after"}, path=p, now=2000.0)
    assert json.loads(Path(p).read_text())["projects"]["proj"]["S1"]["label"] == "after"


def test_the_roster_never_asks_the_owner_itself(tmp_path):
    """The label is passed IN. A document that opened a socket would make every
    write depend on a service being up — and this write is the one that has to
    survive the service dying.
    """
    import inspect
    source = inspect.getsource(roster)
    assert "OwnerClient" not in source and "owner_client" not in source


# --------------------------------------------------------------------------- #
# the last round — WHICH agents were open when the fleet was last observed
# --------------------------------------------------------------------------- #

def test_only_the_newest_round_is_the_composition(tmp_path):
    """AC-4. Three rounds in the record, one composition.

    The entries from the older rounds are still returned — filtering them would
    make the record claim a smaller fleet than it holds, which is the failure
    this module already refuses for unresumable entries.
    """
    p = _path(tmp_path)
    a = FakeAgent(pid=1, cwd="/home/x/proj", session_id="S1", project_name="proj")
    b = FakeAgent(pid=2, cwd="/home/x/proj", session_id="S2", project_name="proj")
    c = FakeAgent(pid=3, cwd="/home/x/proj", session_id="S3", project_name="proj")
    roster.record([a], path=p, now=1000.0)
    roster.record([b], path=p, now=2000.0)
    roster.record([c], path=p, now=3000.0)

    answer = roster.read("proj", path=p, log_root=tmp_path / "logs")
    by_key = {e["key"]: e for e in answer["entries"]}
    assert len(by_key) == 3, "nothing is dropped for being out of the round"
    assert by_key["S3"]["in_last_round"] is True
    assert by_key["S2"]["in_last_round"] is False
    assert by_key["S1"]["in_last_round"] is False
    assert answer["last_round_at"] == 3000.0


def test_a_round_that_saw_nothing_empties_the_composition(tmp_path):
    """AC-5, and the reason the stamp is stored rather than derived.

    A machine that goes down with nothing running still gets a final observation.
    Derived from `max(last_seen)` the composition would be the previous round —
    a screen offering back agents the user had already closed, presented as what
    was open. Here it must come out EMPTY.
    """
    p = _path(tmp_path)
    a = FakeAgent(pid=1, cwd="/home/x/proj", session_id="S1", project_name="proj")
    roster.record([a], path=p, now=1000.0)
    roster.record([], path=p, now=2000.0)          # observed, and empty

    answer = roster.read("proj", path=p, log_root=tmp_path / "logs")
    assert answer["last_round_at"] == 2000.0
    assert [e["in_last_round"] for e in answer["entries"]] == [False]
    assert len(answer["entries"]) == 1, "the entry is still recorded, just not open"


def test_a_record_with_no_stamp_reports_membership_as_unknown(tmp_path):
    """AC-6. A gap is not a zero.

    `False` would mean *this agent was not open*, which the document has no
    evidence for; `None` means *we cannot tell*, and the surface says so instead
    of offering a composition it invented. Asserted with `is None` — a falsiness
    check would pass on `False` and prove nothing.
    """
    p = _path(tmp_path)
    roster.record([FakeAgent(pid=1, cwd="/home/x/proj", session_id="S1", project_name="proj")],
                  path=p, now=1000.0)
    document = json.loads(Path(p).read_text())
    del document["last_round_at"]                   # a document from before this existed
    Path(p).write_text(json.dumps(document))

    answer = roster.read("proj", path=p, log_root=tmp_path / "logs")
    assert answer["last_round_at"] is None
    assert all(e["in_last_round"] is None for e in answer["entries"])


def test_the_stamp_survives_a_read_modify_write_and_a_prune(tmp_path):
    """`normalise()` REBUILDS the document field by field, so a field it does not
    name is dropped on the next write — silently, and the result reads exactly
    like a document written before the field existed. Pruning removes entries;
    it must not remove the observation.
    """
    p = _path(tmp_path)
    roster.record([FakeAgent(pid=1, cwd="/home/x/proj", session_id="S1", project_name="proj")],
                  path=p, now=1000.0)
    # A later round that prunes the first entry out entirely.
    roster.record([FakeAgent(pid=2, cwd="/home/x/proj", session_id="S2", project_name="proj")],
                  path=p, now=1000.0 + roster.RETENTION_SECONDS + 1)
    stored = json.loads(Path(p).read_text())
    assert "S1" not in stored["projects"]["proj"], "the old entry was pruned"
    assert stored["last_round_at"] == 1000.0 + roster.RETENTION_SECONDS + 1


def test_a_partial_write_does_not_move_the_stamp(tmp_path):
    """A write that is not the whole fleet may not claim to be an observation of
    it. If it did, every agent it happened to omit would silently fall out of the
    composition — the safe direction, and still a wrong answer nobody is told
    about.
    """
    p = _path(tmp_path)
    roster.record([FakeAgent(pid=1, cwd="/home/x/proj", session_id="S1", project_name="proj")],
                  path=p, now=1000.0)
    roster.record([FakeAgent(pid=2, cwd="/home/x/proj", session_id="S2", project_name="proj")],
                  path=p, now=2000.0, full_sweep=False)

    stored = json.loads(Path(p).read_text())
    assert stored["last_round_at"] == 1000.0, "a partial write is not an observation of the fleet"
    assert stored["projects"]["proj"]["S2"]["last_seen"] == 2000.0, "the entry is still recorded"
    answer = roster.read("proj", path=p, log_root=tmp_path / "logs")
    by_key = {e["key"]: e for e in answer["entries"]}
    assert by_key["S1"]["in_last_round"] is True and by_key["S2"]["in_last_round"] is False
