"""A declared hand-over in a finished turn — the `fleet-handover-marker` change.

Reported 2026-11-23 from the live screen: a session ended its turn on a line
starting `NEED INPUT:` and the fleet rendered it as an ordinary finished turn.
The marker is the consumer family's own hand-over convention (their keep-going
hook and `set-agent-comm`'s stop hook both read it); these tests hold the
pattern and the class it raises.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.fleet import state as S
from set_orch.fleet.state import read_state

NOW = 1_800_000_000.0


def _record(status, age_seconds=30.0):
    return {"pid": 1, "sessionId": "s", "entrypoint": "cli", "status": status,
            "statusUpdatedAt": (NOW - age_seconds) * 1000.0}


def _log(tmp_path: Path, entries) -> str:
    path = tmp_path / "s.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(path)


def _agent(text):
    return {"type": "assistant", "timestamp": "2026-11-23T20:00:00.000Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def _human(text):
    return {"type": "user", "timestamp": "2026-11-23T20:01:00.000Z",
            "message": {"role": "user", "content": text}}


def _tool_use(tid="t1", name="Bash"):
    return {"type": "assistant", "timestamp": "2026-11-23T19:59:00.000Z",
            "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": name}]}}


def _tool_result(tid="t1"):
    return {"type": "user", "timestamp": "2026-11-23T19:59:30.000Z",
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": "ok"}]}}


ASKS = "Not pushed yet.\n\nNEED INPUT: write „mehet a push” into this session."


def test_a_finished_turn_that_asks_for_input_is_a_prompt(tmp_path):
    st = read_state(_log(tmp_path, [_tool_use(), _tool_result(), _agent(ASKS)]),
                    now=NOW, record=_record("idle"))
    assert st.state == S.QUIET
    assert st.handover == S.HANDOVER_NEED_INPUT
    assert st.attention == S.ATTENTION_PROMPT
    assert st.input_wait_seconds == pytest.approx(30.0)


def test_with_a_background_command_running_it_is_still_a_prompt(tmp_path):
    st = read_state(_log(tmp_path, [_agent(ASKS)]), now=NOW, record=_record("shell"))
    assert st.attention == S.ATTENTION_PROMPT
    assert st.background_running is True


@pytest.mark.parametrize("line", [
    "**NEED INPUT:** decide the name",
    "**NEED INPUT**: decide the name",
    "> NEED INPUT: decide the name",
    "- NEED INPUT: decide the name",
])
def test_markdown_emphasis_does_not_hide_the_marker(tmp_path, line):
    st = read_state(_log(tmp_path, [_agent("Report.\n" + line)]), now=NOW, record=_record("idle"))
    assert st.handover == S.HANDOVER_NEED_INPUT


def test_the_marker_mid_sentence_is_not_a_handover(tmp_path):
    text = "The hook lets a turn that ends on NEED INPUT: through, so nothing is held."
    st = read_state(_log(tmp_path, [_agent(text)]), now=NOW, record=_record("idle"))
    assert st.handover is None
    assert st.attention == S.ATTENTION_INPUT


def test_a_reply_from_the_person_clears_it(tmp_path):
    st = read_state(_log(tmp_path, [_agent(ASKS), _human("mehet a push")]),
                    now=NOW, record=_record("idle"))
    assert st.handover is None
    assert st.attention == S.ATTENTION_INPUT


def test_a_running_turn_is_not_a_handover(tmp_path):
    st = read_state(_log(tmp_path, [_agent(ASKS), _tool_use("t9")]),
                    now=NOW, record=_record("busy"))
    assert st.state == S.WORKING
    assert st.handover is None
    assert st.attention == S.ATTENTION_WORKING


def test_a_marker_before_the_last_tool_call_belongs_to_an_earlier_stretch(tmp_path):
    st = read_state(_log(tmp_path, [_agent(ASKS), _tool_use(), _tool_result(), _agent("Pushed.")]),
                    now=NOW, record=_record("idle"))
    assert st.handover is None


def test_the_closing_message_may_span_several_text_entries(tmp_path):
    st = read_state(_log(tmp_path, [_tool_use(), _tool_result(), _agent(ASKS), _agent("(one more note)")]),
                    now=NOW, record=_record("idle"))
    assert st.handover == S.HANDOVER_NEED_INPUT


def test_a_busy_record_is_not_raised(tmp_path):
    # The log flushed between calls; the loop is running past the marker.
    st = read_state(_log(tmp_path, [_agent(ASKS)]), now=NOW, record=_record("busy"))
    assert st.attention == S.ATTENTION_WORKING


def test_all_done_changes_no_class(tmp_path):
    st = read_state(_log(tmp_path, [_agent("ALL DONE: pushed 8a0e319..98590a6.")]),
                    now=NOW, record=_record("idle"))
    assert st.handover == S.HANDOVER_ALL_DONE
    assert st.attention == S.ATTENTION_INPUT


def test_a_plain_finished_turn_carries_no_handover(tmp_path):
    st = read_state(_log(tmp_path, [_agent("Done, tests green.")]), now=NOW, record=_record("idle"))
    assert st.handover is None
    assert st.attention == S.ATTENTION_INPUT
