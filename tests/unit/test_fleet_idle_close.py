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
