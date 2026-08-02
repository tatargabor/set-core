"""A project names the fields it is willing to have followed; the framework names none.

The temptation this guards against is one line long and looks like a convenience: notice that a
field is called `log`, offer to tail it. That line puts one project's vocabulary inside a
framework built to serve the next one, and the next one calls it `trace`.

So the declaration is read from the envelope and the presence is counted from the DATA — the same
split `caveats` and `deprecated` already use, for the same reason: a declaration is not data, and
a control offered for a field the project stopped sending would offer to follow a path that is
not in the answer.
"""

import json

from set_orch.project_status import follow_targets, parse_envelope


def envelope(data, **extra):
    payload = {"contractVersion": 1, "command": "current", "ok": True, "data": data}
    payload.update(extra)
    return json.dumps(payload)


def test_a_declared_field_is_read_off_the_envelope():
    r = parse_envelope("current", envelope({"running": {"log": "a/b.jsonl"}}, follow=["log"]))
    assert r.ok
    assert r.follow == ("log",)


def test_a_declared_field_present_in_the_data_is_a_target():
    r = parse_envelope("current", envelope({"running": {"log": "a/b.jsonl"}}, follow=["log"]))
    assert follow_targets(r.data, r.follow) == {"log": "a/b.jsonl"}


def test_the_field_is_found_at_any_depth_because_that_is_how_caveats_select():
    data = {"outer": [{"inner": {"trace": "deep/one.log"}}]}
    r = parse_envelope("current", envelope(data, follow=["trace"]))
    assert follow_targets(r.data, r.follow) == {"trace": "deep/one.log"}


def test_a_dotted_key_selects_nothing_and_that_is_the_documented_shape():
    """Held as a test because the failure is silent and points the wrong way.

    A producer writing `follow: ["running.log"]` gets no control and no error, which reads as
    "the framework ignored my declaration" rather than "the key shape is wrong". The rule is one
    selector for the whole envelope; this test is what stops a second one being added quietly.
    """
    r = parse_envelope("current", envelope({"running": {"log": "a/b.jsonl"}},
                                           follow=["running.log"]))
    assert r.follow == ("running.log",)
    assert follow_targets(r.data, r.follow) == {}


def test_an_undeclared_field_holding_a_path_is_not_a_target():
    """The whole point: the value looks exactly like a path, and it is still not followable."""
    r = parse_envelope("current", envelope({"running": {"log": "a/b.jsonl"}}))
    assert r.follow == ()
    assert follow_targets(r.data, r.follow) == {}


def test_a_field_named_log_is_not_recognised_by_the_framework():
    """The mutation guard for D1. Three names a producer might plausibly use, none declared."""
    data = {"log": "a.log", "logFile": "b.log", "trace": "c.log"}
    r = parse_envelope("current", envelope(data))
    assert follow_targets(r.data, r.follow) == {}


def test_a_declared_field_that_is_null_is_nothing_to_follow_and_not_an_error():
    r = parse_envelope("current", envelope({"running": None, "log": None}, follow=["log"]))
    assert r.ok
    assert follow_targets(r.data, r.follow) == {}


def test_a_declared_field_that_is_empty_or_whitespace_is_nothing_to_follow():
    r = parse_envelope("current", envelope({"log": "   "}, follow=["log"]))
    assert follow_targets(r.data, r.follow) == {}


def test_a_declared_field_holding_a_non_string_is_nothing_to_follow():
    """A number or an object is not a path. Refusing it here keeps the gate's job simpler."""
    r = parse_envelope("current", envelope({"log": {"path": "a.log"}}, follow=["log"]))
    assert follow_targets(r.data, r.follow) == {}


def test_a_malformed_declaration_costs_the_decoration_and_never_the_answer():
    """The direction that matters: a broken `follow` must not turn a good answer into a gap."""
    for broken in ("log", {"log": True}, 7):
        r = parse_envelope("current", envelope({"running": {"log": "a.jsonl"}}, follow=broken))
        assert r.ok, f"a malformed 'follow' ({broken!r}) must not refuse the answer"
        assert r.follow == ()


def test_non_string_entries_are_dropped_without_dropping_their_neighbours():
    r = parse_envelope("current", envelope({"log": "a.jsonl"}, follow=[None, 3, "log", ""]))
    assert r.follow == ("log",)


def test_an_absent_declaration_is_the_behaviour_every_project_has_today():
    r = parse_envelope("current", envelope({"running": {"log": "a.jsonl"}}))
    assert r.ok
    assert r.follow == ()


def test_the_first_occurrence_wins_when_a_name_repeats():
    """Stated rather than left to chance: two runs in one answer must not swap under the reader."""
    data = {"a": {"log": "first.jsonl"}, "b": {"log": "second.jsonl"}}
    r = parse_envelope("current", envelope(data, follow=["log"]))
    assert follow_targets(r.data, r.follow) == {"log": "first.jsonl"}


def test_the_transport_carries_the_declaration_or_the_surface_cannot_offer_the_control():
    """A field read correctly and then dropped on the way out is the silent half of this class.

    Everything upstream would be right — the envelope parsed, the fields found — and the screen
    would simply never offer to follow anything, which reads as "the project declared nothing".
    """
    import json as _json
    from set_orch.project_status import StatusResult, StatusSnapshot

    snap = StatusSnapshot()
    snap.results["current"] = StatusResult(
        command="current", ok=True, data={"running": {"log": "a.jsonl"}},
        contract_version=1, follow=("log",),
    )
    payload = snap.to_dict()["commands"]["current"]

    assert payload["follow"] == ["log"]
    # And it must survive JSON, since that is what actually reaches the browser.
    assert _json.loads(_json.dumps(payload))["follow"] == ["log"]
