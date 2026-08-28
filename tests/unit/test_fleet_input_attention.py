"""Is a person needed here, and for how long — the attention axis.

The `fleet-input-attention` change. Kept apart from `test_fleet_state.py`
because it tests a different question against a different source: that file
asks *what is this session stopped on* (the log), this one asks *is the loop
running, and since when* (the runtime record).

Every threshold and every mapping asserted here was measured on 2026-08-28
against runtime 2.1.251 — the measurements are in the module docstring of
`set_orch.fleet.state` and in the change's `design.md`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from set_orch.fleet import state as S
from set_orch.fleet.state import read_state


NOW = 1_800_000_000.0


def _record(status, *, age_seconds=None, **extra):
    rec = {"pid": 4242, "sessionId": "s", "entrypoint": "cli", **extra}
    if status is not None:
        rec["status"] = status
    if age_seconds is not None:
        rec["statusUpdatedAt"] = (NOW - age_seconds) * 1000.0
    return rec


def _finished_turn(tmp_path: Path) -> str:
    path = tmp_path / "finished.jsonl"
    path.write_text(json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}}
    ) + "\n", encoding="utf-8")
    return str(path)


def _outstanding(tmp_path: Path, tool: str = "Bash") -> str:
    path = tmp_path / f"outstanding-{tool}.jsonl"
    path.write_text(json.dumps({
        "type": "assistant", "timestamp": "2026-08-28T00:00:00.000Z",
        "message": {"content": [{"type": "tool_use", "id": "t1", "name": tool}]},
    }) + "\n", encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------------- #
# the four values, and the fifth answer
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("status,expected", [
    ("busy", S.ATTENTION_WORKING),
    ("shell", S.ATTENTION_BACKGROUND),
    ("idle", S.ATTENTION_INPUT),
    ("waiting", S.ATTENTION_PROMPT),
])
def test_each_runtime_status_maps_to_its_own_class(tmp_path, status, expected):
    st = read_state(_finished_turn(tmp_path), now=NOW, record=_record(status, age_seconds=30))
    assert st.attention == expected
    assert st.runtime_status == status


def test_a_backgrounded_command_is_not_a_person_waiting(tmp_path):
    """AC-3, and the reason this whole axis exists.

    `shell` is computed by the runtime as `idle AND a background bash is
    running`. A session in it looks exactly like a finished turn from the log —
    no call outstanding — and writing to it is not what it needs.
    """
    st = read_state(_finished_turn(tmp_path), now=NOW, record=_record("shell", age_seconds=600))
    assert st.attention == S.ATTENTION_BACKGROUND
    assert st.background_running is True
    # The duration is deliberately absent: it is not waiting for anybody, so a
    # number here would be rendered as a wait by any caller that trusts the field.
    assert st.input_wait_seconds is None
    assert S.tone_for(st.input_wait_seconds) is None


def test_a_permission_prompt_carries_its_reason_verbatim(tmp_path):
    st = read_state(
        _finished_turn(tmp_path), now=NOW,
        record=_record("waiting", age_seconds=5, waitingFor="permission prompt"),
    )
    assert st.attention == S.ATTENTION_PROMPT
    assert st.waiting_for == "permission prompt"


def test_a_headless_run_carrying_no_status_is_unmeasured_not_idle(tmp_path):
    """AC-5. Measured 2026-08-28 on runtime 2.1.251, and unchanged since the
    first measurement ten days earlier: `claude -p` registers a record with
    `entrypoint: "sdk-cli"` and NO `status` key at all.

    The fail direction is the point. Reading absence as `idle` would put a
    working orchestration agent on the screen as a person's problem, and the
    reader acts on that by interrupting work that was fine.
    """
    st = read_state(
        _finished_turn(tmp_path), now=NOW,
        record=_record(None, entrypoint="sdk-cli", statusUpdatedAt=(NOW - 900) * 1000.0),
    )
    assert st.attention == S.ATTENTION_UNMEASURED
    assert st.input_wait_seconds is None


def test_a_headless_record_is_not_an_UNRECOGNISED_status(tmp_path, caplog):
    """A missing key is a gap, not a surprise. Warning about it would fire on
    every headless agent in the fleet, which is how a real warning stops being
    read."""
    with caplog.at_level("WARNING"):
        read_state(_finished_turn(tmp_path), now=NOW,
                   record=_record(None, entrypoint="sdk-cli"))
    assert "status this build does not know" not in caplog.text


def test_no_record_at_all_is_unmeasured(tmp_path):
    st = read_state(_finished_turn(tmp_path), now=NOW, record=None)
    assert st.attention == S.ATTENTION_UNMEASURED
    assert st.runtime_status is None


def test_a_status_this_build_does_not_know_is_unmeasured_and_says_so(tmp_path, caplog):
    """A renamed value in a future runtime must not land on a neighbour.

    Mapping an unknown status onto `idle` would make the fleet look like it went
    quiet; onto `busy`, like it went silent. Both are calm readings of an event
    that is really *we stopped understanding the source*.
    """
    with caplog.at_level("WARNING"):
        st = read_state(
            _finished_turn(tmp_path), now=NOW, record=_record("hibernating", age_seconds=10)
        )
    assert st.attention == S.ATTENTION_UNMEASURED
    assert "hibernating" in caplog.text


def test_an_empty_status_is_unmeasured_without_a_warning(tmp_path, caplog):
    """Absent and empty are the same answer — nobody wrote one down — and neither
    deserves the alarm that an unrecognised VALUE does."""
    with caplog.at_level("WARNING"):
        st = read_state(_finished_turn(tmp_path), now=NOW, record=_record("", age_seconds=10))
    assert st.attention == S.ATTENTION_UNMEASURED
    assert "status this build does not know" not in caplog.text


# --------------------------------------------------------------------------- #
# where the duration comes from
# --------------------------------------------------------------------------- #

def test_an_idle_stamp_hours_old_is_the_length_of_the_wait(tmp_path):
    """AC-1, and it is the correction of a decision this repo took on 2026-08-18.

    An eleven-hour-old `idle` stamp was read as a stale field. It is a correctly
    recorded eleven-hour wait: the runtime writes the record when the status
    CHANGES, so the stamp is the age of the state.
    """
    st = read_state(_finished_turn(tmp_path), now=NOW, record=_record("idle", age_seconds=7200))
    assert st.attention == S.ATTENTION_INPUT
    assert st.input_wait_seconds == pytest.approx(7200, abs=1)


def test_the_logs_mtime_does_not_shorten_the_wait(tmp_path):
    """AC-2 — the exact shape measured in 2 of 10 live sessions on 2026-08-28:
    the log FILE was rewritten (mtime moved) while its newest entry stayed put,
    up to 90 minutes apart. A wait taken from mtime would have read as fresh.
    """
    log = _finished_turn(tmp_path)
    # The file is touched NOW; the record says the session went idle an hour ago.
    Path(log).touch()
    st = read_state(log, now=time.time(), record={
        "status": "idle", "statusUpdatedAt": (time.time() - 3600) * 1000.0,
    })
    assert st.input_wait_seconds == pytest.approx(3600, abs=5)
    # And the file's own age is still reported, under its own name, unchanged.
    assert st.last_movement_age < 5


def test_a_stamp_from_the_future_is_zero_not_negative(tmp_path):
    """Two machines' clocks, or one machine's clock moving. A negative wait sorts
    ahead of every real one and renders as a countdown."""
    st = read_state(_finished_turn(tmp_path), now=NOW, record=_record("idle", age_seconds=-60))
    assert st.input_wait_seconds == 0.0


def test_a_record_without_a_stamp_reports_the_class_and_no_duration(tmp_path):
    """The class is still known; only the age is not. Substituting zero would put
    a genuinely long wait in the calmest band."""
    st = read_state(_finished_turn(tmp_path), now=NOW, record=_record("idle"))
    assert st.attention == S.ATTENTION_INPUT
    assert st.input_wait_seconds is None
    assert S.tone_for(st.input_wait_seconds) is None


# --------------------------------------------------------------------------- #
# the measurement outranks the record
# --------------------------------------------------------------------------- #

def test_an_outstanding_question_tool_wins_over_an_idle_record(tmp_path):
    """AC-6. The log names a specific outstanding call; the record only says the
    loop is not running. The more specific claim wins, and both agree a person
    is needed anyway."""
    st = read_state(
        _outstanding(tmp_path, "AskUserQuestion"), now=NOW,
        record=_record("idle", age_seconds=30),
    )
    assert st.state == "asking"
    assert st.attention == S.ATTENTION_PROMPT


def test_an_asking_agent_with_no_record_still_gets_a_duration(tmp_path):
    """How long the question has been open is measurable from the log alone, and
    it is the honest fallback when the record says nothing."""
    st = read_state(_outstanding(tmp_path, "AskUserQuestion"), now=NOW, record=None)
    assert st.attention == S.ATTENTION_PROMPT
    assert st.input_wait_seconds is not None


def test_an_outstanding_call_beats_an_idle_record_and_names_the_disagreement(tmp_path):
    """AC-7. Until 2026-08-28 only a `waiting` record was named as contradicted,
    so the far more common `idle` disagreement was invisible — a contradiction
    nobody can see is one nobody will fix.
    """
    st = read_state(_outstanding(tmp_path), now=NOW, record=_record("idle", age_seconds=30))
    assert st.state == "working"
    assert st.attention == S.ATTENTION_WORKING
    assert st.declaration_ignored == "idle"
    assert st.input_wait_seconds is None


# --------------------------------------------------------------------------- #
# the escalation
# --------------------------------------------------------------------------- #

def test_the_three_bands():
    assert S.tone_for(9) == S.TONE_PLAIN       # AC-8
    assert S.tone_for(45) == S.TONE_AMBER      # AC-9
    assert S.tone_for(240) == S.TONE_RED       # AC-10


def test_the_band_edges_are_where_the_user_put_them():
    """LITERAL seconds, not the constants.

    Written this way after a mutation round: moving the thresholds to 20 s and
    200 s left `test_the_three_bands` green, because 9 / 45 / 240 stay in the
    same bands on either side. A boundary test phrased in terms of the constant
    it is checking asserts the mechanism and is silent about the result.
    """
    assert S.tone_for(14.9) == S.TONE_PLAIN
    assert S.tone_for(15.0) == S.TONE_AMBER
    assert S.tone_for(15.1) == S.TONE_AMBER
    assert S.tone_for(179.9) == S.TONE_AMBER
    assert S.tone_for(180.0) == S.TONE_RED
    assert S.tone_for(180.1) == S.TONE_RED


def test_an_unmeasured_wait_has_no_tone_rather_than_the_calmest_one():
    assert S.tone_for(None) is None


def test_the_thresholds_are_the_numbers_the_user_asked_for():
    """Held in a test because they are a decision, not an implementation detail:
    15 seconds to notice, 3 minutes to shout."""
    assert S.INPUT_WAIT_AMBER_SECONDS == 15
    assert S.INPUT_WAIT_RED_SECONDS == 180
