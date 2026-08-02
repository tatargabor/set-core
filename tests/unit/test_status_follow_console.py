"""One console line per transcript record — and what a console must not spend itself on.

The measurement behind this file: a live transcript held 123 records, and 47 of them were the
same `system` bookkeeping event. Every one rendered as a bare label with no numbers, so 38% of
the console said nothing at all — which is exactly the question the user asked about it.
"""

import json

from set_orch.api.status_follow import _console_line, _repeat_key


def record(**kw):
    return json.dumps(kw)


BOOKKEEPING = record(
    at="2026-08-02T15:21:12.028Z", type="system", subtype="thinking_tokens",
    estimated_tokens=1250, estimated_tokens_delta=50, uuid="u", session_id="s",
)


def test_a_record_with_no_text_carries_its_numbers():
    """A bookkeeping record exists FOR its numbers; printing only the label discards the record."""
    line = _console_line(BOOKKEEPING)
    assert "estimated_tokens=1,250" in line
    assert "estimated_tokens_delta=50" in line


def test_a_NUMERIC_identity_field_is_still_not_a_measurement():
    """The version of this that passed for the wrong reason asserted on `uuid` and `session_id`.

    Both are strings, so the numeric filter excluded them and the envelope-field list was never
    exercised — emptying that list left the test green. A millisecond timestamp is the real case:
    a number, routing rather than data, and it would otherwise render as `timestamp=1,785,684,064,827`
    beside the measurement someone is trying to read.
    """
    line = _console_line(record(
        type="system", subtype="thinking_tokens",
        timestamp=1785684064827, estimated_tokens=1250,
    ))
    assert "estimated_tokens=1,250" in line
    assert "timestamp" not in line


def test_numbers_are_read_by_shape_not_by_a_list_of_known_names():
    """A hard-coded field list would be a second copy of someone else's schema, and would drift
    the first time that schema grew a field."""
    line = _console_line(record(type="system", subtype="brand_new_metric", whatever_count=7))
    assert "whatever_count=7" in line


def test_consecutive_bookkeeping_records_share_a_fold_key():
    assert _repeat_key(BOOKKEEPING) == "system·thinking_tokens"


def test_a_different_subtype_does_not_fold_into_the_previous_one():
    other = record(type="system", subtype="hook_started", uuid="z")
    assert _repeat_key(other) != _repeat_key(BOOKKEEPING)


def test_a_TOOL_CALL_is_never_folded_however_often_it_repeats():
    """The load-bearing negative. Two identical `Bash` calls are two events; a console that
    merged them would have lost the second one — and that is a loss no count can undo.

    It is also where this shipped broken: `iter_tool_uses` returns a GENERATOR, and a generator
    object is always truthy, so the original guard passed for EVERY record and the function
    returned None for all of them. No fold, no error, nothing on screen to say so.
    """
    tool = record(type="assistant", message={
        "content": [{"type": "tool_use", "name": "Bash", "input": {}}],
    })
    assert _repeat_key(tool) is None


def test_a_record_with_TEXT_is_never_folded():
    """Carries a SUBTYPE deliberately: without one the subtype guard rejects it first, and the
    text guard — the thing this test names — is never reached. That version passed while the
    text check was deleted."""
    said = record(
        type="assistant", subtype="message",
        message={"content": [{"type": "text", "text": "hello"}]},
    )
    assert _repeat_key(said) is None, "a record that SAID something is an event, not bookkeeping"


def test_a_record_without_a_subtype_is_not_foldable():
    """Without a subtype there is nothing to say two records are the SAME kind of nothing."""
    assert _repeat_key(record(type="rate_limit_event", at="x")) is None


def test_a_line_that_is_not_a_transcript_record_passes_through_unfolded():
    assert _repeat_key("plain log line") is None
    assert _console_line("plain log line") is None
