"""Bringing a recorded list back, and the four ways an entry can fail to come.

The property under test throughout is that **an entry that does not start says
why**, and that the reasons are distinguishable. A restore of nine that starts
three is a partial result; the single most likely defect in this feature is a
green "Restored" over six agents that never came back.

No real agent is started anywhere here. The owner is a fake that records what it
was asked for — which is also what lets the tests assert that a LIVE session was
never asked about at all, rather than asked and refused.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from set_orch.fleet import discovery, restore as restore_mod, roster
from set_orch.fleet.owner_client import OwnerClientError, OwnerUnavailable


class FakeOwner:
    """Records every call. Refuses only what it is told to refuse."""

    def __init__(self, *, held: Optional[List[str]] = None,
                 refuse: Optional[Dict[str, str]] = None,
                 healthy: bool = True, list_raises: bool = False):
        self.held = list(held or [])
        self.refuse = dict(refuse or {})
        self.healthy = healthy
        self.list_raises = list_raises
        self.recovered: List[Dict[str, Any]] = []
        self.pid = 1000

    def health(self):
        if not self.healthy:
            raise OwnerUnavailable("the agent owner is not running")
        return {"ok": True}

    def list_agents(self):
        if self.list_raises:
            raise OwnerClientError("no")
        return [{"label": l} for l in self.held]

    def recover(self, *, unit, session_id, cwd, label=None, resume_argv=None,
                provider_unit=None):
        self.recovered.append({"unit": unit, "session_id": session_id, "cwd": cwd,
                               "label": label, "resume_argv": resume_argv,
                               "provider_unit": provider_unit})
        if session_id in self.refuse:
            raise OwnerClientError(self.refuse[session_id])
        self.pid += 1
        return {"label": label, "pid": self.pid, "unit": unit}


class _A:
    def __init__(self, cwd, session_id, name, kind="interactive", pid=1):
        self.pid, self.cwd, self.session_id = pid, cwd, session_id
        self.name, self.project_name, self.kind = name, os.path.basename(cwd), kind


def _seed(tmp_path, sessions, *, with_logs=True, project="proj"):
    """A roster and (optionally) the transcripts that make its entries resumable."""
    cwd = tmp_path / project
    cwd.mkdir(exist_ok=True)
    path = str(tmp_path / "store" / "fleet-roster.json")
    # One pid per session, and a LABEL for each: since 2026-08-21 the record
    # stores the label the framework holds, so a fixture that only sets the
    # runtime's `name` seeds entries with no label at all — which is a real
    # state (an agent the framework never held) and not the one most of these
    # tests are about.
    agents = [_A(str(cwd), s, f"{project}-{s.lower()}", pid=i) for i, s in enumerate(sessions, 1)]
    roster.record(agents, labels={a.pid: a.name for a in agents}, path=path, now=1000.0)
    logs = tmp_path / "projects"
    if with_logs:
        d = logs / f"-{project}"
        d.mkdir(parents=True, exist_ok=True)
        for s in sessions:
            (d / f"{s}.jsonl").write_text("{}\n")
    return path, logs, str(cwd)


@pytest.fixture(autouse=True)
def _transcripts_and_liveness(monkeypatch, tmp_path):
    """Default: transcripts are found, nothing is live. Each test narrows this."""
    monkeypatch.setattr(discovery, "SESSION_LOG_ROOT", tmp_path / "projects")
    monkeypatch.setattr(discovery, "live_session_ids", lambda: set())


# --------------------------------------------------------------------------- #
# the whole list, one outcome each
# --------------------------------------------------------------------------- #

def test_every_recorded_entry_gets_exactly_one_outcome(tmp_path, monkeypatch):
    """AC-14."""
    path, logs, cwd = _seed(tmp_path, ["S1", "S2", "S3"])
    owner = FakeOwner()
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert out["attempted"] == 3
    assert len(out["started"]) + len(out["skipped"]) + len(out["failed"]) == 3
    assert {o["session_id"] for o in out["started"]} == {"S1", "S2", "S3"}
    assert out["complete"] is True


def test_an_empty_record_starts_nothing(tmp_path):
    """AC-15."""
    owner = FakeOwner()
    out = restore_mod.restore("nobody", client=owner,
                              roster_path=str(tmp_path / "store" / "fleet-roster.json"))
    assert out["attempted"] == 0 and owner.recovered == []
    assert out["record_exists"] is False


def test_a_resumable_entry_is_resumed_in_its_own_cwd(tmp_path):
    """AC-16, and the argv: none is passed, so the owner's own default is used
    and cannot drift from what a bare interactive session gets.
    """
    path, logs, cwd = _seed(tmp_path, ["S1"])
    owner = FakeOwner()
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert len(owner.recovered) == 1
    call = owner.recovered[0]
    assert call["session_id"] == "S1" and call["cwd"] == cwd
    assert call["resume_argv"] is None, "restore must not carry its own argv"
    assert out["started"][0]["pid"] == 1001


# --------------------------------------------------------------------------- #
# the silent failure this exists to prevent
# --------------------------------------------------------------------------- #

def test_a_live_session_is_never_even_asked_about(tmp_path, monkeypatch):
    """AC-18 — asserted as ABSENCE OF THE CALL, not as a handled refusal.

    A test that let the call through and checked the error would pass on code
    that forks the conversation and reports it tidily.
    """
    path, logs, cwd = _seed(tmp_path, ["LIVE", "DEAD"])
    monkeypatch.setattr(discovery, "live_session_ids", lambda: {"LIVE"})
    owner = FakeOwner()
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})

    assert [c["session_id"] for c in owner.recovered] == ["DEAD"], \
        "the live session was handed to the owner"
    (skip,) = out["skipped"]
    assert skip["session_id"] == "LIVE"
    assert "live process" in skip["reason"] and "forks" in skip["reason"]
    assert out["complete"] is False


def test_indeterminate_liveness_is_treated_as_live(tmp_path, monkeypatch):
    """AC-19. `live_session_ids()` returns None when it cannot look — every
    other reader flattens that to "no agents", which here would read as
    "nothing is running" and clear the way.
    """
    path, logs, cwd = _seed(tmp_path, ["S1"])
    monkeypatch.setattr(discovery, "live_session_ids", lambda: None)
    owner = FakeOwner()
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert owner.recovered == [], "an unknowable liveness must not become a resume"
    assert "indeterminate" in out["skipped"][0]["reason"] or \
           "cannot determine" in out["skipped"][0]["reason"]


def test_an_empty_live_set_is_not_the_same_as_none(tmp_path, monkeypatch):
    """The negative control for the test above: with an EMPTY set — meaning
    'we looked, nothing is running' — the same entry must start. Without this,
    a restore that never starts anything would satisfy the test above.
    """
    path, logs, cwd = _seed(tmp_path, ["S1"])
    monkeypatch.setattr(discovery, "live_session_ids", lambda: set())
    owner = FakeOwner()
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert len(out["started"]) == 1


# --------------------------------------------------------------------------- #
# skipped, with the reason that distinguishes it
# --------------------------------------------------------------------------- #

def test_an_entry_with_no_transcript_is_skipped_not_failed(tmp_path):
    """AC-20. `failed` invites a retry; there is nothing to retry."""
    path, logs, cwd = _seed(tmp_path, ["S1"], with_logs=False)
    owner = FakeOwner()
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert out["failed"] == [] and len(out["skipped"]) == 1
    assert "transcript" in out["skipped"][0]["reason"]
    assert owner.recovered == []


def test_an_entry_whose_directory_is_gone_is_skipped_with_that_reason(tmp_path):
    path, logs, cwd = _seed(tmp_path, ["S1"])
    os.rmdir(cwd)
    owner = FakeOwner()
    out = restore_mod.restore("proj", client=owner, roster_path=path, known_roots=None)
    assert "directory is gone" in out["skipped"][0]["reason"]
    assert owner.recovered == []


def test_a_cwd_outside_the_known_roots_is_refused_here_too(tmp_path):
    """Measurement M2: `POST /api/fleet/agents` refuses a cwd outside the known
    roots. A second route that admits what the first refuses is the guard being
    deleted one caller at a time.
    """
    path, logs, cwd = _seed(tmp_path, ["S1"])
    owner = FakeOwner()
    out = restore_mod.restore("proj", client=owner, roster_path=path, known_roots=set())
    assert owner.recovered == []
    assert "not a project this screen knows" in out["skipped"][0]["reason"]


# --------------------------------------------------------------------------- #
# partial results, and one failure not abandoning the rest
# --------------------------------------------------------------------------- #

def test_a_mixed_restore_reports_its_three_parts(tmp_path, monkeypatch):
    """AC-21. Nine entries: 3 start, 4 skip for three DIFFERENT reasons, 2 fail."""
    cwd = tmp_path / "proj"; cwd.mkdir()
    path = str(tmp_path / "store" / "fleet-roster.json")
    sessions = ["OK1", "OK2", "OK3", "LIVE1", "LIVE2", "NOLOG1", "NOLOG2", "BAD1", "BAD2"]
    roster.record([_A(str(cwd), s, f"proj-{s.lower()}") for s in sessions],
                  path=path, now=1000.0)
    logs = tmp_path / "projects" / "-proj"
    logs.mkdir(parents=True)
    for s in sessions:
        if not s.startswith("NOLOG"):
            (logs / f"{s}.jsonl").write_text("{}\n")
    monkeypatch.setattr(discovery, "live_session_ids", lambda: {"LIVE1", "LIVE2"})

    owner = FakeOwner(refuse={"BAD1": "scope will not die", "BAD2": "scope will not die"})
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(str(cwd))})

    assert out["attempted"] == 9
    assert len(out["started"]) == 3, out["started"]
    assert len(out["skipped"]) == 4
    assert len(out["failed"]) == 2
    assert out["complete"] is False
    assert all(o["reason"] for o in out["skipped"] + out["failed"]), \
        "every entry that did not start must carry a reason"
    reasons = {o["session_id"]: o["reason"] for o in out["skipped"]}
    assert "live process" in reasons["LIVE1"]
    assert "transcript" in reasons["NOLOG1"]


def test_one_failure_does_not_abandon_the_rest(tmp_path):
    """AC-22. The entries after a refusal are still attempted."""
    path, logs, cwd = _seed(tmp_path, ["A", "BAD", "C"])
    owner = FakeOwner(refuse={"BAD": "no"})
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert {o["session_id"] for o in out["started"]} == {"A", "C"}
    assert out["failed"][0]["session_id"] == "BAD"


def test_complete_is_false_whenever_anything_did_not_start(tmp_path, monkeypatch):
    """The flag exists so a surface cannot render a partial restore as a whole
    one by counting only `started`.
    """
    path, logs, cwd = _seed(tmp_path, ["A", "LIVE"])
    monkeypatch.setattr(discovery, "live_session_ids", lambda: {"LIVE"})
    out = restore_mod.restore("proj", client=FakeOwner(), roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert len(out["started"]) == 1 and out["complete"] is False


# --------------------------------------------------------------------------- #
# the owner
# --------------------------------------------------------------------------- #

def test_an_unreachable_owner_fails_the_whole_request_before_anything_is_tried(tmp_path):
    """AC-17. Nothing was attempted, so a result listing N failures would say
    something different from the truth.
    """
    path, logs, cwd = _seed(tmp_path, ["S1", "S2"])
    owner = FakeOwner(healthy=False)
    with pytest.raises(OwnerUnavailable):
        restore_mod.restore("proj", client=owner, roster_path=path,
                            known_roots={os.path.realpath(cwd)})
    assert owner.recovered == []


def test_a_held_label_is_renamed_and_the_rename_is_reported(tmp_path):
    """Task 5.4, settled against the owner's MEASURED behaviour: it refuses a
    label it already holds (`owner.py:150`), and `list` returns what it holds —
    so the collision is avoided proactively rather than by matching an error
    string.
    """
    path, logs, cwd = _seed(tmp_path, ["S1"])
    owner = FakeOwner(held=["proj-s1"])
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    started = out["started"][0]
    assert started["label_used"] == "proj-s1-r2"
    assert started["renamed"] is True, "a rename must be visible, not silent"


def test_a_label_that_is_free_is_not_renamed(tmp_path):
    path, logs, cwd = _seed(tmp_path, ["S1"])
    out = restore_mod.restore("proj", client=FakeOwner(), roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert out["started"][0]["renamed"] is False
    assert out["started"][0]["label_used"] == "proj-s1"


def test_an_owner_that_cannot_list_labels_does_not_stop_the_restore(tmp_path):
    """Not knowing what is held must not block a restore — the owner refuses a
    duplicate itself, and that authority is not optional.
    """
    path, logs, cwd = _seed(tmp_path, ["S1"])
    owner = FakeOwner(list_raises=True)
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert len(out["started"]) == 1


# --------------------------------------------------------------------------- #
# the routes
# --------------------------------------------------------------------------- #

def test_the_roster_routes_are_registered_and_distinct():
    """Four routes, four paths, and the listing route is not shadowed by the
    per-project one — a `GET /api/fleet/roster` that resolved to `{project}`
    would answer the empty screen's question with a project named "roster".
    """
    from set_orch.api.fleet import router
    found = {(tuple(sorted(r.methods)), r.path) for r in router.routes
             if "roster" in getattr(r, "path", "")}
    assert (("GET",), "/api/fleet/roster") in found
    assert (("GET",), "/api/fleet/roster/{project}") in found
    assert (("POST",), "/api/fleet/roster/{project}/restore") in found
    assert (("DELETE",), "/api/fleet/roster/{project}/{key:path}") in found
    paths = [r.path for r in router.routes if "roster" in getattr(r, "path", "")]
    assert paths.index("/api/fleet/roster") < paths.index("/api/fleet/roster/{project}"), \
        "the listing route must be declared before the wildcard that would swallow it"


def test_the_restore_route_takes_a_project_and_a_selection_and_nothing_else():
    """Narrower than the owner socket on purpose. A signature carrying an argv, a
    cwd or a label would make this a general-purpose start route wearing a
    restore's name — and that is still refused. What it may carry, since
    2026-08-26, is WHICH recorded entries to bring back.
    """
    import inspect
    from set_orch.api.fleet import fleet_roster_restore, RestoreBody
    params = inspect.signature(fleet_roster_restore).parameters
    assert list(params) == ["project", "body"], f"unexpected parameters: {list(params)}"
    assert params["body"].default is None, "the body must be optional — a bodiless POST is the whole list"
    assert set(RestoreBody.model_fields) == {"keys"}, \
        f"the body may name entries and nothing else: {set(RestoreBody.model_fields)}"


def test_an_unreachable_owner_is_a_503_from_the_route(monkeypatch, tmp_path):
    """AC-17 at the route: nothing was attempted, so this is one answer about
    the request rather than N answers about N entries.
    """
    from fastapi import HTTPException
    from set_orch.api import fleet as fleet_api

    def _down(*a, **k):
        raise OwnerUnavailable("the agent owner is not running")

    monkeypatch.setattr(fleet_api.fleet_restore, "restore", _down)
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: set())
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_roster_restore("proj")
    assert excinfo.value.status_code == 503


def test_forgetting_an_entry_that_is_not_there_is_a_404(monkeypatch):
    from fastapi import HTTPException
    from set_orch.api import fleet as fleet_api
    monkeypatch.setattr(fleet_api.roster, "forget", lambda *a, **k: False)
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_roster_forget("proj", "S1")
    assert excinfo.value.status_code == 404


def test_the_route_passes_the_known_roots_through(monkeypatch):
    """The guard is supplied by the layer that knows the registry, and the fleet
    layer stays domain-free. A route that forgot to pass it would restore into
    directories `POST /api/fleet/agents` refuses.
    """
    from set_orch.api import fleet as fleet_api
    seen = {}
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {"/a", "/b"})
    monkeypatch.setattr(fleet_api.fleet_restore, "restore",
                        lambda project, **kw: seen.update(kw) or {"attempted": 0})
    fleet_api.fleet_roster_restore("proj")
    assert seen.get("known_roots") == {"/a", "/b"}


# --------------------------------------------------------------------------- #
# which name came back — AC-17 … AC-19
# --------------------------------------------------------------------------- #

def test_a_restored_entry_says_the_name_survived_the_reboot(tmp_path):
    """AC-17. `started` alone cannot answer the question a person actually has
    when they look at a restored fleet: is this the name I gave it?
    """
    path, logs, cwd = _seed(tmp_path, ["S1"])
    out = restore_mod.restore("proj", client=FakeOwner(), roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    started = out["started"][0]
    assert started["name_source"] == restore_mod.RESTORED
    assert started["label_used"] == "proj-s1" and started["wanted_label"] == "proj-s1"


def test_an_entry_with_no_recorded_label_says_its_name_was_derived(tmp_path):
    """AC-18. The framework never held this agent, so nobody named it. A derived
    name presented as a restored one is the false value this change exists
    against — in the one place a person looks to recognise their own work.
    """
    cwd = tmp_path / "proj"
    cwd.mkdir()
    path = str(tmp_path / "store" / "fleet-roster.json")
    roster.record([_A(str(cwd), "S1", "proj-ab")], labels={}, path=path, now=1000.0)
    d = tmp_path / "projects" / "-proj"
    d.mkdir(parents=True, exist_ok=True)
    (d / "S1.jsonl").write_text("{}\n")

    out = restore_mod.restore("proj", client=FakeOwner(), roster_path=path,
                              known_roots={os.path.realpath(str(cwd))})
    started = out["started"][0]
    assert started["name_source"] == restore_mod.DERIVED
    assert started["label_used"] == "proj-restored"
    assert "proj-ab" not in json.dumps(out), "the runtime's derived name is not a name anybody chose"


def test_a_collision_reports_both_the_wanted_and_the_used_name(tmp_path):
    """AC-19. Restore derives where a rename refuses — the asymmetry is
    deliberate: here the alternative is losing the agent, with nobody watching.
    """
    path, logs, cwd = _seed(tmp_path, ["S1"])
    out = restore_mod.restore("proj", client=FakeOwner(held=["proj-s1"]), roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    started = out["started"][0]
    assert started["name_source"] == restore_mod.RENAMED
    assert (started["wanted_label"], started["label_used"]) == ("proj-s1", "proj-s1-r2")


# --------------------------------------------------------------------------- #
# the selection — absent, empty and populated are three different requests
# --------------------------------------------------------------------------- #

def test_no_selection_still_attempts_the_whole_record(tmp_path):
    """AC-7, and the regression this change must not cause: `keys=None` is what
    every existing caller passes by not passing anything.
    """
    owner = FakeOwner()
    path, _, cwd = _seed(tmp_path, ["S1", "S2", "S3"])
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert out["attempted"] == 3 and len(out["started"]) == 3


def test_a_selection_attempts_exactly_that_selection(tmp_path):
    """AC-8. The others are not attempted AT ALL — asserted against the owner's
    own record of what it was asked for, not against the outcome list, because a
    skipped outcome and an unattempted entry read alike from the result.
    """
    owner = FakeOwner()
    path, _, cwd = _seed(tmp_path, ["S1", "S2", "S3"])
    out = restore_mod.restore("proj", keys=["S1", "S3"], client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert out["attempted"] == 2
    assert {o["session_id"] for o in out["started"]} == {"S1", "S3"}
    assert {r["session_id"] for r in owner.recovered} == {"S1", "S3"}, "S2 was never asked about"
    assert out["complete"] is True


def test_an_empty_selection_attempts_nothing(tmp_path):
    """AC-9. The `keys or entries` fallback would turn "restore none" into
    "restore all", which on a record holding a month of conversations is the
    exact act this selection exists to prevent.
    """
    owner = FakeOwner()
    path, _, cwd = _seed(tmp_path, ["S1", "S2", "S3"])
    out = restore_mod.restore("proj", keys=[], client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert out["attempted"] == 0
    assert owner.recovered == [], "nothing was asked for, so nothing may be started"


def test_a_selected_key_that_is_not_recorded_is_reported(tmp_path):
    """AC-10. Filtering the entries by the selection would make this key vanish,
    and the result would then report fewer attempts than were asked for while
    reading like a complete restore.
    """
    owner = FakeOwner()
    path, _, cwd = _seed(tmp_path, ["S1"])
    out = restore_mod.restore("proj", keys=["S1", "GHOST"], client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    assert out["attempted"] == 2
    assert len(out["started"]) == 1
    ghost = [o for o in out["skipped"] if o["key"] == "GHOST"]
    assert len(ghost) == 1 and "nothing is recorded" in ghost[0]["reason"]
    assert out["complete"] is False, "an unrecognised key is not a completed restore"


def test_the_route_passes_the_selection_through(monkeypatch):
    """AC-8 at the route, and AC-7 beside it: a bodiless POST must still mean the
    whole list. A route that defaulted the body to an empty selection would turn
    every existing caller into a no-op — silently, and in the direction that
    looks like success.
    """
    from set_orch.api import fleet as fleet_api
    seen: Dict[str, Any] = {}
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: set())
    monkeypatch.setattr(fleet_api.fleet_restore, "restore",
                        lambda project, **kw: seen.update(kw) or {"attempted": 0})

    fleet_api.fleet_roster_restore("proj")
    assert seen["keys"] is None, "no body means the whole recorded list"

    fleet_api.fleet_roster_restore("proj", fleet_api.RestoreBody(keys=["S1", "S2"]))
    assert seen["keys"] == ["S1", "S2"]

    fleet_api.fleet_roster_restore("proj", fleet_api.RestoreBody(keys=[]))
    assert seen["keys"] == [], "an empty selection is not an absent one"


# --------------------------------------------------------------------------- #
# peeking at a recorded session — read, never resumed (B-80's other half)
# --------------------------------------------------------------------------- #

def _transcript(tmp_path, session_id, turns, *, project="proj"):
    """Write a transcript the way the runtime writes one, for one recorded session."""
    d = tmp_path / "projects" / f"-{project}"
    d.mkdir(parents=True, exist_ok=True)
    log = d / f"{session_id}.jsonl"
    log.write_text("\n".join(
        json.dumps({"type": "user" if i % 2 == 0 else "assistant",
                    "timestamp": f"2026-08-26T10:{i:02d}:00Z",
                    "message": {"content": [{"type": "text", "text": t}]}})
        for i, t in enumerate(turns)) + "\n")
    return log


def test_a_recorded_session_is_readable_without_being_resumed(tmp_path):
    """AC-1. The owner is asserted to have been asked NOTHING: a read that
    happens to start an agent would look identical in the payload.
    """
    from set_orch.api import fleet as fleet_api
    owner = FakeOwner()
    path, _, _ = _seed(tmp_path, ["S1"], with_logs=False)
    _transcript(tmp_path, "S1", ["first", "second", "third"])
    monkey = fleet_api.roster.read
    try:
        fleet_api.roster.read = lambda project, **kw: monkey(project, path=path, **kw)
        out = fleet_api.fleet_roster_peek("proj", "S1", limit=2)
    finally:
        fleet_api.roster.read = monkey
    assert [t["text"] for t in out["turns"]] == ["second", "third"]
    assert out.get("problem") is None
    assert out["limit"] == 2 and out["key"] == "S1"
    assert owner.recovered == [], "a read must not start anything"


def test_a_long_transcript_answers_the_bound_and_says_there_is_more(tmp_path):
    """AC-2. `truncated` is what stops a six-turn answer from reading as the
    whole of a two-hundred-turn conversation.
    """
    from set_orch.api import fleet as fleet_api
    path, _, _ = _seed(tmp_path, ["S1"], with_logs=False)
    _transcript(tmp_path, "S1", [f"turn-{i}" for i in range(200)])
    real = fleet_api.roster.read
    try:
        fleet_api.roster.read = lambda project, **kw: real(project, path=path, **kw)
        out = fleet_api.fleet_roster_peek("proj", "S1", limit=6)
    finally:
        fleet_api.roster.read = real
    assert len(out["turns"]) == 6
    assert out["turns"][-1]["text"] == "turn-199"
    assert out["truncated"] is True and out["total_read"] == 200


def test_an_entry_with_no_transcript_says_so_rather_than_reading_as_empty(tmp_path):
    """AC-3 and AC-4. Two different absences, two different sentences — and
    neither is an empty `turns` with no problem, which means exactly one thing:
    the transcript was read and holds no conversation.
    """
    from set_orch.api import fleet as fleet_api
    path, _, _ = _seed(tmp_path, ["S1"], with_logs=False)          # no transcript
    roster.record([_A(str(tmp_path / "proj"), None, "proj-nameless", pid=9)],
                  labels={9: "proj-nameless"}, path=path, now=1000.0)
    real = fleet_api.roster.read
    try:
        fleet_api.roster.read = lambda project, **kw: real(project, path=path, **kw)
        gone = fleet_api.fleet_roster_peek("proj", "S1", limit=6)
        nameless = fleet_api.fleet_roster_peek("proj", "no-session:proj/proj-nameless", limit=6)
    finally:
        fleet_api.roster.read = real
    assert gone["turns"] == [] and "no transcript on disk" in gone["problem"]
    # The wording changed with `roster-session-identity`: the old line —
    # "no session id was ever recorded for this agent" — was a DENIAL, and false
    # for an agent the framework had started on a known session. What this test
    # asserts is unchanged: two different absences, two different sentences.
    assert nameless["turns"] == [] and "no source knows a session" in nameless["problem"]
    assert gone["problem"] != nameless["problem"], "two absences, two sentences"
    # The sentence is the entry's own, so the panel and the row beside it cannot
    # disagree about why this conversation is not there.
    assert gone["problem"] == real("proj", path=path)["entries"][0]["not_resumable_reason"] \
        or any(e["not_resumable_reason"] == gone["problem"] for e in real("proj", path=path)["entries"])


def test_peeking_at_an_unrecorded_key_is_a_404(tmp_path):
    """AC-5. Not in the record and recorded-but-unreadable are different facts,
    and only the second one describes an agent.
    """
    from fastapi import HTTPException
    from set_orch.api import fleet as fleet_api
    path, _, _ = _seed(tmp_path, ["S1"], with_logs=False)
    real = fleet_api.roster.read
    try:
        fleet_api.roster.read = lambda project, **kw: real(project, path=path, **kw)
        with pytest.raises(HTTPException) as excinfo:
            fleet_api.fleet_roster_peek("proj", "GHOST", limit=6)
    finally:
        fleet_api.roster.read = real
    assert excinfo.value.status_code == 404


def test_the_peek_is_not_cached(tmp_path):
    """AC-7, asserted by MUTATING the source between two reads.

    A cache would make the second answer identical, and a cache of transcript
    content is the confidentiality boundary being crossed — the framework may
    read a project's data and must hold none of it.
    """
    from set_orch.api import fleet as fleet_api
    path, _, _ = _seed(tmp_path, ["S1"], with_logs=False)
    _transcript(tmp_path, "S1", ["before"])
    real = fleet_api.roster.read
    try:
        fleet_api.roster.read = lambda project, **kw: real(project, path=path, **kw)
        first = fleet_api.fleet_roster_peek("proj", "S1", limit=6)
        _transcript(tmp_path, "S1", ["before", "after"])
        second = fleet_api.fleet_roster_peek("proj", "S1", limit=6)
    finally:
        fleet_api.roster.read = real
    assert [t["text"] for t in first["turns"]] == ["before"]
    assert [t["text"] for t in second["turns"]] == ["before", "after"]


def test_the_peek_route_holds_no_module_level_store():
    """AC-6/AC-7 structurally: a memo added later would pass every test above on
    its first call and fail the boundary silently on the second.
    """
    import inspect
    from set_orch.api import fleet as fleet_api
    # The DOCSTRING is stripped before the check, because it says the word
    # "cached" while promising the opposite — and a test that reads prose as
    # code is this repo's own named defect class.
    source = inspect.getsource(fleet_api.fleet_roster_peek)
    body = source.split('"""')[-1]
    for forbidden in ("lru_cache", "cache", "_PEEK", "global "):
        assert forbidden not in body, f"the peek must hold nothing: found {forbidden!r}"
