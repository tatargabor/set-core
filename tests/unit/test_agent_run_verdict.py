"""A failed RUN is not a bad ANSWER, and the CLI says which — in a field nobody was reading.

Adopted from an integration peer who measured the same misattribution on their own engine:
their loop died on a stalled stream and the engine reported "the model's answer contained no
parseable JSON block". The two need opposite responses — a stalled stream is retryable, a bad
answer questions the prompt — so reporting the second for the first sends someone to rewrite a
prompt that was fine while the retryable failure goes unretried.
"""

import json

import pytest

from set_orch.subprocess_utils import _result_status_from_json_output


def envelope(**kw):
    return json.dumps({"type": "result", **kw})


def test_a_clean_run_reports_no_error():
    assert _result_status_from_json_output(envelope(subtype="success", is_error=False)) == (
        False, "success",
    )


def test_the_MEASURED_case_success_label_with_the_error_flag_set():
    """Found in real transcripts, and it is why the flag outranks the label.

    An envelope arrived carrying `subtype: "success"` AND `is_error: true`. A reader trusting
    the word would have called that run a success — the reassuring direction, on the one field
    that decides between retrying and rewriting.
    """
    is_error, subtype = _result_status_from_json_output(
        envelope(subtype="success", is_error=True),
    )
    assert is_error is True
    assert subtype == "success", "the label is carried verbatim, never corrected to match"


def test_a_named_failure_carries_its_own_word():
    assert _result_status_from_json_output(
        envelope(subtype="error_max_turns", is_error=True),
    ) == (True, "error_max_turns")


def test_output_that_is_not_a_transcript_reports_nothing_rather_than_a_failure():
    """Fail direction: an unreadable stream must not become a reported error, or every
    non-JSON caller starts failing for a reason that never happened."""
    assert _result_status_from_json_output("plain text\nnot json") == (False, None)
    assert _result_status_from_json_output("") == (False, None)


def test_an_error_anywhere_in_the_stream_survives_a_later_clean_envelope():
    """Streams carry several objects. An error reported once is not undone by a later line."""
    raw = "\n".join([
        envelope(subtype="error_during_execution", is_error=True),
        envelope(subtype="success", is_error=False),
    ])
    is_error, _ = _result_status_from_json_output(raw)
    assert is_error is True


def test_records_that_are_not_the_result_envelope_are_ignored():
    raw = "\n".join([
        json.dumps({"type": "assistant", "is_error": True}),
        envelope(subtype="success", is_error=False),
    ])
    assert _result_status_from_json_output(raw) == (False, "success")


def test_the_planner_names_a_failed_run_differently_from_an_unparseable_answer():
    """The whole point is the WORDING a human reads next. Held as a test because the two
    messages are one sentence apart in the source and trivially collapsed back into one."""
    import inspect
    from set_orch import planner

    src = inspect.getsource(planner)
    assert src.count("the agent run failed") >= 4, (
        "every planner phase that parses an agent answer must first report a failed RUN"
    )
    assert "could not parse" in src, "the answer-level failure still has its own wording"
