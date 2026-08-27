"""Where a recorded agent's session identity comes from, and how long a row lives.

`tests/unit/test_fleet_roster.py` covers the record's reboot-faithfulness and is
untouched by the `roster-session-identity` change; this file is the two facts
that were not reaching it.

The measurement both halves stand on, taken with `set-fleet-roster` on a real
machine on 2026-08-27: **8 entries, 6 un-restorable, 4 of them session-less** —
and three of those four were ONE live session recorded under successive pids,
each left behind when the runtime's record finally appeared and a second entry
was written under the real session id.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from set_orch.fleet import roster


@dataclass
class FakeAgent:
    """Only what the roster is allowed to read — same rule as the sibling suite:
    if it ever starts reading something else, this fake stops providing it."""

    pid: int
    cwd: str
    session_id: Optional[str] = None
    name: Optional[str] = None
    project_name: Optional[str] = None
    kind: str = "interactive"


def _path(tmp_path) -> str:
    return str(tmp_path / "store" / "fleet-roster.json")


def _stored(tmp_path, project="proj") -> dict:
    return json.loads(Path(_path(tmp_path)).read_text())["projects"].get(project, {})


# --------------------------------------------------------------------------- #
# where the identity comes from
# --------------------------------------------------------------------------- #

def test_the_runtimes_answer_wins_over_the_frameworks(tmp_path):
    """The order is not arbitrary. The runtime says what the process is BOUND to;
    the framework says what it was ASKED to resume. The case that produced this
    defect is one where they disagree — an agent told to resume a session it
    could not claim — and there the process's own answer is the one being asked
    about."""
    roster.record(
        [FakeAgent(pid=42, cwd="/x/proj", session_id="RUNTIME", project_name="proj")],
        sessions={42: "ASKED-FOR"},
        path=_path(tmp_path), now=1000.0,
    )
    assert set(_stored(tmp_path)) == {"RUNTIME"}


def test_the_frameworks_answer_fills_a_silence(tmp_path):
    """The reported defect, in one assertion. An agent the framework started with
    `--resume <S>` whose runtime record never appeared was keyed as having no
    session at all — while the owner was reporting `<S>` for that same pid."""
    roster.record(
        [FakeAgent(pid=9289, cwd="/x/proj", project_name="proj")],
        sessions={9289: "S"},
        path=_path(tmp_path), now=1000.0,
    )
    keys = set(_stored(tmp_path))
    assert keys == {"S"}
    assert not any(k.startswith(roster.NO_SESSION_KEY_PREFIX) for k in keys)


def test_neither_source_knows(tmp_path):
    roster.record(
        [FakeAgent(pid=7, cwd="/x/proj", project_name="proj")],
        sessions={99: "someone-elses"},
        path=_path(tmp_path), now=1000.0,
    )
    [key] = list(_stored(tmp_path))
    assert key.startswith(roster.NO_SESSION_KEY_PREFIX)


def test_an_unreachable_framework_keeps_the_restorable_row_and_adds_a_throwaway_one(tmp_path):
    """What an unreachable framework actually costs, asserted rather than assumed.

    ⚠ Two earlier versions of this test proved nothing, and both failure modes
    are worth keeping:

    1. It asserted that `None`, `{}` and "not supplied" produce the same keys.
       True BY CONSTRUCTION — `(sessions or {}).get(pid)` cannot tell them apart —
       so a mutation collapsing the two passed.
    2. It then asserted that an unreachable framework cannot erase a recorded
       session. Also true by construction, and for a reason that makes the test
       hollow: the key IS the session, so a row keyed `S` is only ever rewritten
       by a sighting that already knows `S`. A mutation that cleared the field on
       every update passed, because that row was never touched.

    The roster genuinely cannot observe the difference between `None` and `{}`.
    Where the distinction lives is the caller — see the API test below — and in
    the warning it logs. What IS observable here is the consequence: the agent
    grows a SECOND, session-less row, while the restorable one survives. That is
    the right direction (nothing that could be acted on is lost) and the extra
    row is retired as soon as the agent stops being seen.
    """
    agent = FakeAgent(pid=9289, cwd="/x/proj", project_name="proj")
    roster.record([agent], sessions={9289: "S"}, path=_path(tmp_path), now=1000.0)
    assert set(_stored(tmp_path)) == {"S"}

    roster.record([agent], sessions=None, path=_path(tmp_path), now=1010.0)
    stored = _stored(tmp_path)
    assert "S" in stored, "the restorable row did not survive an unreachable framework"
    assert stored["S"]["session_id"] == "S"
    assert any(k.startswith(roster.NO_SESSION_KEY_PREFIX) for k in stored)

    # ...and the throwaway row goes as soon as the agent is no longer seen.
    roster.record([], path=_path(tmp_path), now=1020.0, full_sweep=True)
    assert set(_stored(tmp_path)) == {"S"}


def test_the_listing_passes_an_unreachable_owner_through_as_unknown(monkeypatch):
    """The other half, and it lives at the caller. The roster cannot tell `None`
    from `{}`; the API must not turn the first into the second on the way in,
    because that is where "could not ask" would become "asked, holds nothing"."""
    from set_orch.api import fleet as api

    seen = {}
    monkeypatch.setattr(api.roster, "record",
                        lambda agents, **kw: seen.update(kw) or {"added": 0})
    api._record_roster([], None)
    assert seen["labels"] is None
    assert seen["sessions"] is None

    seen.clear()
    api._record_roster([], {})
    assert seen["labels"] == {}
    assert seen["sessions"] == {}


def test_the_roster_never_opens_a_socket_to_the_owner(tmp_path):
    """Held as a test rather than as the docstring's promise. The module's own
    rule: a document that opened a socket to the agent owner would make every
    write depend on a service being up."""
    source = Path(roster.__file__).read_text()
    assert "OwnerClient" not in source
    assert "owner_client" not in source


# --------------------------------------------------------------------------- #
# the reason a reader acts on
# --------------------------------------------------------------------------- #

def test_a_session_less_entry_names_both_sources_rather_than_denying_a_record(tmp_path):
    """The previous wording — "no session id was ever recorded for this agent" —
    was a DENIAL, and false for the one case that mattered: the framework had
    recorded one, at the moment it started the agent, and was reporting it
    elsewhere on the same screen."""
    roster.record(
        [FakeAgent(pid=7, cwd="/x/proj", project_name="proj")],
        path=_path(tmp_path), now=1000.0,
    )
    [entry] = roster.read("proj", path=_path(tmp_path), log_root=tmp_path / "logs")["entries"]
    assert entry["resumable"] is False
    assert "was ever recorded" not in entry["not_resumable_reason"]
    assert "no source knows a session" in entry["not_resumable_reason"]
    assert "the framework did not start it" in entry["not_resumable_reason"]


# --------------------------------------------------------------------------- #
# the key builder, as it actually behaves
# --------------------------------------------------------------------------- #

def test_the_no_session_key_falls_back_to_the_pid(tmp_path):
    """Its docstring claimed the key is derived "never from its pid". It is,
    whenever there is no name — which is every agent the runtime has not yet
    recorded, i.e. exactly the population this key exists for."""
    key = roster._no_session_key(FakeAgent(pid=9289, cwd="/x/proj", project_name="proj"))
    assert key.endswith("pid-9289")


def test_the_no_session_key_changes_when_a_name_appears(tmp_path):
    """The other half of the same false claim: "stable across sightings". One
    agent could therefore leave more than one row behind. Not repaired — a row of
    this kind now lives only while its agent is seen, so an unstable key produces
    one row at a time instead of a permanent pair."""
    before = roster._no_session_key(FakeAgent(pid=9289, cwd="/x/proj", project_name="proj"))
    after = roster._no_session_key(
        FakeAgent(pid=9289, cwd="/x/proj", project_name="proj", name="proj-a5"))
    assert before != after


# --------------------------------------------------------------------------- #
# how long a row lives
# --------------------------------------------------------------------------- #

def _seed_sessionless(tmp_path, now=1000.0):
    roster.record(
        [FakeAgent(pid=7, cwd="/x/proj", project_name="proj"),
         FakeAgent(pid=8, cwd="/x/proj", project_name="proj", session_id="KEEP")],
        path=_path(tmp_path), now=now,
    )
    keys = set(_stored(tmp_path))
    assert any(k.startswith(roster.NO_SESSION_KEY_PREFIX) for k in keys)
    assert "KEEP" in keys


def test_an_unseen_session_less_row_is_retired_by_a_whole_fleet_write(tmp_path):
    """The accumulation, measured at 4 of 8 rows. A row of this kind can never be
    acted on, so its lifetime is the sighting rather than the retention window."""
    _seed_sessionless(tmp_path)
    roster.record(
        [FakeAgent(pid=8, cwd="/x/proj", project_name="proj", session_id="KEEP")],
        path=_path(tmp_path), now=1010.0, full_sweep=True,
    )
    assert set(_stored(tmp_path)) == {"KEEP"}


def test_a_row_that_could_be_acted_on_is_never_retired_this_way(tmp_path):
    """The pair that makes the rule safe. Only rows the read path already marks
    unresumable-for-want-of-a-session go; a row with a session survives an
    absence, because a machine that was off is not a fleet that died."""
    _seed_sessionless(tmp_path)
    roster.record([], path=_path(tmp_path), now=1010.0, full_sweep=True)
    assert set(_stored(tmp_path)) == {"KEEP"}


def test_a_still_seen_session_less_row_is_kept_with_its_first_seen_intact(tmp_path):
    _seed_sessionless(tmp_path)
    agent = FakeAgent(pid=7, cwd="/x/proj", project_name="proj")
    roster.record([agent], path=_path(tmp_path), now=1010.0, full_sweep=True)
    stored = _stored(tmp_path)
    [row] = [v for k, v in stored.items() if k.startswith(roster.NO_SESSION_KEY_PREFIX)]
    assert row["first_seen"] == 1000.0
    assert row["last_seen"] == 1010.0


def test_a_partial_write_retires_nothing(tmp_path):
    """A partial write knows nothing about what it did not look at, so removing
    on absence would delete live agents' rows. The same flag already guards the
    round stamp, for the same reason."""
    _seed_sessionless(tmp_path)
    roster.record(
        [FakeAgent(pid=8, cwd="/x/proj", project_name="proj", session_id="KEEP")],
        path=_path(tmp_path), now=1010.0, full_sweep=False,
    )
    keys = set(_stored(tmp_path))
    assert any(k.startswith(roster.NO_SESSION_KEY_PREFIX) for k in keys)


def test_a_partial_write_still_records_what_it_did_see(tmp_path):
    roster.record(
        [FakeAgent(pid=8, cwd="/x/proj", project_name="proj", session_id="NEW")],
        path=_path(tmp_path), now=1000.0, full_sweep=False,
    )
    assert "NEW" in _stored(tmp_path)


def test_the_age_bound_still_governs_a_row_that_carries_a_session(tmp_path, caplog):
    _seed_sessionless(tmp_path)
    with caplog.at_level("INFO"):
        roster.record([], path=_path(tmp_path), now=1000.0 + 31 * 24 * 3600, full_sweep=True)
    assert _stored(tmp_path) == {}
    assert any("pruning KEEP" in r.getMessage() for r in caplog.records)


def test_a_retirement_is_logged_rather_than_silent(tmp_path, caplog):
    """An entry that vanishes without a line is indistinguishable from one that
    was never written — the reason the age prune logs too."""
    _seed_sessionless(tmp_path)
    with caplog.at_level("INFO"):
        roster.record(
            [FakeAgent(pid=8, cwd="/x/proj", project_name="proj", session_id="KEEP")],
            path=_path(tmp_path), now=1010.0, full_sweep=True,
        )
    assert any("retiring" in r.getMessage() and "could never have been restored" in r.getMessage()
               for r in caplog.records)
