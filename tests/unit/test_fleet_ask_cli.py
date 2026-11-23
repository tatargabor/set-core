"""`set-fleet-ask`: resolve the desk, send as the asker, report — against a fake API and bus.

The properties a caller relies on: the request text goes to the bus and never to the
dashboard, a refusal sends nothing, a failed send is recorded as failed, and every failure
path exits non-zero with the reason.
"""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest

from set_orch.fleet import ask_cli

MARKER = "ZZ-REQUEST-MARKER-ZZ"
SEAT = "alpha#aaaaaaaa"
SESSION = "aaaaaaaa-0000-4000-8000-000000000001"
DESK = {"project": "beta", "label": "beta-desk", "seat": "beta#0000dddd",
        "mandate_id": "m-1", "started": True, "pid": 900}


class Api:
    def __init__(self, resolve=(200, {"engagement_id": "e-1", "desk": DESK}), sent=(200, {}), listing=None):
        self.calls, self.resolve, self.sent, self.listing = [], resolve, sent, listing

    def __call__(self, method, path, body, timeout):
        self.calls.append((method, path, body))
        if path == "/api/fleet/desks/resolve":
            return self.resolve
        if path.endswith("/sent"):
            return self.sent
        if path.endswith("/failed"):
            return 200, {}
        if path.startswith("/api/fleet/engagements?"):
            return self.listing
        raise AssertionError(path)


class Bus:
    """`sac agents --json` and `sac send`, recorded."""

    def __init__(self, send_ok=True, seats=((SEAT, SESSION),), send_stdout=None):
        self.calls, self.send_ok, self.seats, self.send_stdout = [], send_ok, seats, send_stdout

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        if argv[1] == "agents":
            return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps({"agents": [
                {"agent": "alpha", "seats": [{"seat": s, "session": sid} for s, sid in self.seats]}]}))
        if argv[1] == "send":
            if not self.send_ok:
                return SimpleNamespace(returncode=1, stdout="", stderr="sac: send refused\nsac: no such seat")
            out = self.send_stdout if self.send_stdout is not None else json.dumps(
                {"ts": "2026-11-23T19:50:05.598+01:00", "room": "dm-alpha--beta", "wakes": [DESK["seat"]]})
            return SimpleNamespace(returncode=0, stdout=out, stderr="")
        raise AssertionError(argv)


def _ask(api, bus, **over):
    out, err = io.StringIO(), io.StringIO()
    args = dict(seat=SEAT, http=api, run=bus, out=out, err=err)
    args.update(over)
    code = ask_cli.ask("beta", f"please {MARKER} this", **args)
    return code, out.getvalue(), err.getvalue()


def test_a_request_is_resolved_sent_as_the_asker_and_reported():
    api, bus = Api(), Bus()
    code, out, _err = _ask(api, bus, subject="the export format")
    assert code == 0
    # 1. resolve — with the asker's seat and the subject, and WITHOUT the request text.
    method, path, body = api.calls[0]
    assert (method, path) == ("POST", "/api/fleet/desks/resolve")
    assert body == {"project": "beta", "requested_by": SEAT, "kind": "REQUEST", "subject": "the export format"}
    # 2. the bus send, addressed to the desk's SEAT (not the project name).
    assert bus.calls == [["sac", "send", "REQUEST", f"please {MARKER} this", "--to", "beta#0000dddd"]]
    # 3. the pointer goes back.
    assert api.calls[1] == ("POST", "/api/fleet/engagements/e-1/sent",
                            {"room": "dm-alpha--beta", "ts": "2026-11-23T19:50:05.598+01:00"})
    assert "e-1" in out and "beta#0000dddd" in out and "started for this request" in out


def test_the_request_text_never_reaches_the_dashboard():
    api, bus = Api(), Bus()
    _ask(api, bus, subject="short label")
    assert MARKER not in json.dumps(api.calls)


def test_a_question_is_sent_as_a_question():
    api, bus = Api(), Bus()
    _ask(api, bus, kind="QUESTION")
    assert api.calls[0][2]["kind"] == "QUESTION" and bus.calls[0][2] == "QUESTION"


def test_a_long_subject_is_cut_and_flattened():
    api, bus = Api(), Bus()
    _ask(api, bus, subject="line one\nline two " + "x" * 200)
    subject = api.calls[0][2]["subject"]
    assert "\n" not in subject and len(subject) <= ask_cli.SUBJECT_MAX


@pytest.mark.parametrize("status,payload,expect", [
    (409, {"detail": {"reason": "not-on-bus", "detail": "beta is not enrolled", "engagement_id": "e-9"}}, "not-on-bus"),
    (409, {"detail": {"reason": "archived", "detail": "beta is archived"}}, "archived"),
    (0, {"detail": "the dashboard could not be reached"}, "could not be reached"),
])
def test_a_refused_resolution_sends_nothing_and_says_why(status, payload, expect):
    api, bus = Api(resolve=(status, payload)), Bus()
    code, out, err = _ask(api, bus)
    assert code == 1 and expect in err and out == ""
    assert bus.calls == [] and len(api.calls) == 1


def test_the_bound_lists_what_is_open():
    api = Api(resolve=(429, {"detail": {"reason": "bound", "detail": "5 open; the bound is 5", "open": [
        {"id": "e-3", "project": "gamma", "state": "open", "age_seconds": 120.4, "subject": "old one"}]}}))
    code, _out, err = _ask(api, Bus())
    assert code == 1 and "bound" in err and "e-3" in err and "gamma" in err and "old one" in err


@pytest.mark.parametrize("bus", [
    Bus(send_ok=False),
    Bus(send_stdout="not json"),
    Bus(send_stdout=json.dumps({"ts": "x"})),          # no room: not a pointer
])
def test_a_send_the_bus_did_not_make_fails_the_engagement(bus):
    api = Api()
    code, out, err = _ask(api, bus)
    assert code == 1 and out == "" and "not sent" in err
    assert api.calls[1] == ("POST", "/api/fleet/engagements/e-1/failed", {"reason": "send-failed"})
    assert not any(path.endswith("/sent") for _m, path, _b in api.calls)


def test_a_request_on_the_bus_is_a_success_even_if_the_record_lags():
    api = Api(sent=(500, {"detail": "boom"}))
    code, out, err = _ask(api, Bus())
    assert code == 0 and "e-1" in out and "not recorded as open" in err


def test_the_asker_s_seat_is_found_by_its_session_id():
    bus = Bus(seats=(("alpha#bbbbbbbb", "other-session"), (SEAT, SESSION)))
    assert ask_cli.own_seat(SESSION, run=bus) == SEAT
    assert ask_cli.own_seat("no-such-session", run=bus) is None
    assert ask_cli.own_seat(None, run=bus) is None

    def missing(argv, **kw):
        raise FileNotFoundError("sac")

    assert ask_cli.own_seat(SESSION, run=missing) is None


def test_a_session_with_no_seat_is_told_to_enrol_and_nothing_is_asked(monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "no-such-session")
    api, bus = Api(), Bus()
    assert ask_cli.main(["beta", "please"], http=api, run=bus) == 3
    assert api.calls == [] and "no seat on the bus" in capsys.readouterr().err


def test_main_asks_with_the_looked_up_seat(monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION)
    api, bus = Api(), Bus()
    assert ask_cli.main(["beta", "please do it", "--question"], http=api, run=bus) == 0
    assert api.calls[0][2]["requested_by"] == SEAT and api.calls[0][2]["kind"] == "QUESTION"


@pytest.mark.parametrize("argv", [[], ["beta"], ["beta", "   "]])
def test_usage_errors_ask_nothing(monkeypatch, argv, capsys):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION)
    api = Api()
    assert ask_cli.main(argv, http=api, run=Bus()) == 2
    assert api.calls == []


def test_the_list_shows_state_age_and_the_waiting_mark(monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION)
    api = Api(listing=(200, {"measured": False, "engagements": [
        {"id": "e-1", "state": "open", "project": "beta", "age_seconds": 3700.2, "waiting": True, "subject": "export"},
        {"id": "e-2", "state": "unmeasured", "project": "gamma", "age_seconds": 12, "waiting": False, "subject": None},
    ]}))
    assert ask_cli.main(["--list"], http=api, run=Bus()) == 0
    out = capsys.readouterr().out
    assert "e-1" in out and "waiting" in out and "3700" in out and "export" in out
    assert "e-2" in out and "unmeasured" in out and "could not be read" in out
    assert api.calls[0][1] == "/api/fleet/engagements?asker=alpha%23aaaaaaaa"
