"""Closing long-idle fleet agents: who is closed, who is kept and why, and what is recorded.

`run()` is driven against a real local HTTP server that answers the listing and the stop route the
way the dashboard does (including the 404 for an agent it does not hold), so the stop path is
exercised end to end rather than through a stubbed function.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.fleet import idle_close as ic  # noqa: E402

H = 3600


def agent(label, human_h, *, move_h=0.1, kind="interactive", tool=None, runtime="idle", project="p"):
    return {
        "pid": abs(hash(label or "x")) % 100000, "kind": kind, "terminal_label": label,
        "project": project, "session_id": f"sid-{label}",
        "last_human_input_seconds": None if human_h is None else human_h * H,
        "last_movement_seconds": move_h * H, "tool": tool, "runtime_status": runtime,
    }


class Fleet:
    def __init__(self, agents, missing=()):
        self.agents = agents
        self.missing = set(missing)
        self.stopped = []


@pytest.fixture
def fleet():
    state = Fleet([])

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            self._send(200, {"projects": [{"name": "p", "agents": state.agents}]})

        def do_POST(self):  # noqa: N802
            label = self.path.split("/api/fleet/agents/")[1].rsplit("/stop", 1)[0]
            if label in state.missing:
                self._send(404, {"detail": f"no agent named {label} is running"})
                return
            state.stopped.append(label)
            self._send(200, {"label": label, "found": True, "gone": True})

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    state.url = f"http://127.0.0.1:{srv.server_address[1]}"
    yield state
    srv.shutdown()


def test_the_signal_is_owner_input_not_movement():
    # AC-1, AC-2, AC-3: idle past the threshold closes even if a watch woke it a minute ago.
    assert ic.classify(agent("a", 60, move_h=0.02), 48 * H) == ic.CLOSE
    assert ic.classify(agent("b", 10, move_h=30), 48 * H) == ic.KEEP_RECENT
    assert ic.classify(agent("c", 48, move_h=99), 48 * H) == ic.KEEP_RECENT   # the boundary keeps


def test_doubt_keeps_the_agent():
    # AC-4, AC-5, and the two reasons the stop route could not or must not be used.
    assert ic.classify(agent("u", None), 48 * H) == ic.KEEP_UNMEASURED
    assert ic.classify(agent("t", 90, tool="Bash"), 48 * H) == ic.KEEP_BUSY
    assert ic.classify(agent("r", 90, runtime="busy"), 48 * H) == ic.KEEP_BUSY
    assert ic.classify(agent(None, 90), 48 * H) == ic.UNREACHABLE
    assert ic.classify(agent("o", 90, kind="orchestration"), 48 * H) == ic.NOT_INTERACTIVE
    bad = agent("s", 90)
    bad["last_human_input_seconds"] = "90h"
    assert ic.classify(bad, 48 * H) == ic.KEEP_UNMEASURED


def test_a_dry_run_sends_no_stop(fleet, tmp_path):
    # AC-6
    fleet.agents = [agent("old1", 60), agent("old2", 100), agent("new", 1)]
    log = tmp_path / "log.jsonl"
    out = ic.run(fleet.url, threshold_s=48 * H, dry_run=True, log_file=log)
    assert sorted(r["label"] for r in out["closed"]) == ["old1", "old2"]
    assert fleet.stopped == []
    assert not log.exists()


def test_closes_are_stopped_and_logged_and_a_404_is_a_failure(fleet, tmp_path):
    # AC-7, AC-8
    fleet.agents = [agent("old", 60), agent("gone", 70), agent("busy", 80, tool="Edit"), agent("new", 2)]
    fleet.missing = {"gone"}
    log = tmp_path / "state" / "log.jsonl"
    out = ic.run(fleet.url, threshold_s=48 * H, log_file=log)

    assert fleet.stopped == ["old"]
    assert [r["label"] for r in out["closed"]] == ["old"]
    assert [(r["label"], r["error"]) for r in out["failed"]] == [("gone", "HTTP 404")]
    assert [r["label"] for r in out["kept_busy"]] == ["busy"]
    assert out["recent"] == 1

    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(r["label"], r["session_id"], r["idle_hours"]) for r in rows] == [("old", "sid-old", 60.0)]
    assert oct(log.stat().st_mode & 0o777) == "0o600"


def test_the_threshold_comes_from_the_option_then_local_config(monkeypatch, tmp_path):
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv(ic.local_config.env_key(ic.CONFIG_KEY), raising=False)
    assert ic.threshold_hours() == 48.0
    ic.local_config.set_value(ic.CONFIG_KEY, 24)
    assert ic.threshold_hours() == 24.0
    assert ic.threshold_hours(6) == 6.0
    ic.local_config.set_value(ic.CONFIG_KEY, "two days")
    with pytest.raises(ValueError):
        ic.threshold_hours()


def test_an_unreachable_listing_closes_nothing(tmp_path, capsys):
    rc = ic.main(["--base-url", "http://127.0.0.1:9", "--hours", "1"])
    assert rc == 1
    assert "nothing was closed" in capsys.readouterr().err


def test_install_timer_writes_a_daily_enabled_timer(tmp_path):
    # AC-9
    calls = []
    where = ic.install_timer("/opt/x/set-fleet-idle-close", "04:00", unit_dir=tmp_path,
                             systemctl=lambda argv, check: calls.append(argv))
    service = (where / "set-fleet-idle-close.service").read_text()
    timer = (where / "set-fleet-idle-close.timer").read_text()
    assert "ExecStart=/opt/x/set-fleet-idle-close" in service
    assert "OnCalendar=*-*-* 04:00:00" in timer and "Persistent=true" in timer
    assert ["systemctl", "--user", "enable", "--now", "set-fleet-idle-close.timer"] in calls


# --------------------------------------------------------------------------- #
# The fleet screen's view: status, upcoming, the log, the switch
# --------------------------------------------------------------------------- #

def test_upcoming_counts_the_time_until_the_next_run():
    agents = [agent("soon", 40), agent("over", 60, tool="Bash"), agent("fresh", 2), agent(None, 90),
              agent("unk", None)]
    # 10 hours until the run: 40 h idle becomes 50 h > 48 h.
    rows = ic.upcoming(agents, 48 * H, 10 * H)
    assert [(r["label"], r["busy"]) for r in rows] == [("over", True), ("soon", False)]
    # With no run ahead (timer off), only what is already past the threshold.
    assert [r["label"] for r in ic.upcoming(agents, 48 * H, None)] == ["over"]


def test_read_log_is_newest_first_and_skips_bad_lines(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text('{"session_id":"a","label":"A"}\nnot json\n{"session_id":"b","label":"B"}\n{"no":"sid"}\n')
    assert [r["label"] for r in ic.read_log(log)] == ["B", "A"]
    assert ic.read_log(tmp_path / "missing.jsonl") == []


def _runner(enabled_word, timers_json, calls=None):
    class R:
        def __init__(self, out, err=""):
            self.stdout, self.stderr, self.returncode = out, err, 0

    def run(argv, **kw):
        if calls is not None:
            calls.append(argv)
        if "is-enabled" in argv:
            return R(enabled_word + "\n")
        if "list-timers" in argv:
            return R(timers_json)
        return R("")
    return run


def test_timer_state_reads_enabled_next_and_last():
    t = ic.timer_state(_runner("enabled", json.dumps([{"unit": "set-fleet-idle-close.timer",
                                                        "next": 1_794_106_800_000_000, "last": 0}])))
    assert t == {"known": True, "installed": True, "enabled": True, "next_run": 1_794_106_800.0, "last_run": None}
    off = ic.timer_state(_runner("disabled", "[]"))
    assert off["installed"] is True and off["enabled"] is False and off["next_run"] is None
    missing = ic.timer_state(_runner("not-found", "[]"))
    assert missing["installed"] is False


def test_timer_state_unreadable_is_not_disabled():
    def boom(argv, **kw):
        raise FileNotFoundError("systemctl")
    t = ic.timer_state(boom)
    assert t["known"] is False and t["enabled"] is None


def test_switching_on_installs_once_then_enables(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    ic.set_enabled(True, runner=_runner("not-found", "[]", calls), command="/x/set-fleet-idle-close")
    assert (tmp_path / "systemd" / "user" / "set-fleet-idle-close.timer").exists()
    calls.clear()
    ic.set_enabled(False, runner=_runner("enabled", "[]", calls))
    assert ["systemctl", "--user", "disable", "--now", "set-fleet-idle-close.timer"] in calls


def test_status_marks_closed_sessions_that_are_running_again():
    out = ic.status([agent("soon", 47)], threshold_s=48 * H,
                    timer={"enabled": True, "next_run": 1000.0 + 2 * H},
                    closed=[{"session_id": "s1", "label": "x"}, {"session_id": "s2", "label": "y"}],
                    live_ids={"s2"}, now=1000.0)
    assert [r["label"] for r in out["upcoming"]] == ["soon"]
    assert [(r["label"], r["running"]) for r in out["closed"]] == [("x", False), ("y", True)]
    unknown = ic.status([], threshold_s=48 * H, timer={}, closed=[{"session_id": "s1"}], live_ids=None, now=0)
    assert unknown["closed"][0]["running"] is None and unknown["liveness_known"] is False


def test_the_api_answers_status_and_refuses_a_silly_threshold(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from set_orch.api import fleet as fleet_api
    from set_orch.server import create_app

    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(fleet_api, "fleet_agents", lambda include_oneshot=False: {
        "projects": [{"name": "p", "agents": [agent("old", 60)]}]})
    monkeypatch.setattr(fleet_api, "fleet_live_session_ids", lambda: set())
    monkeypatch.setattr(ic, "timer_state", lambda runner=None: {
        "known": True, "installed": True, "enabled": True, "next_run": None, "last_run": None})
    client = TestClient(create_app(web_dist_dir=None))

    d = client.get("/api/fleet/idle-close").json()
    assert d["threshold_hours"] == 48.0 and [r["label"] for r in d["upcoming"]] == ["old"]
    assert client.post("/api/fleet/idle-close", json={"hours": 1}).status_code == 422
    assert client.post("/api/fleet/idle-close", json={"bogus": 1}).status_code == 422
    d = client.post("/api/fleet/idle-close", json={"hours": 72}).json()
    assert d["threshold_hours"] == 72.0 and d["upcoming"] == []
