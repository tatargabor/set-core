"""`/api/fleet/watchdog` — summary, mute, dispatch-now (change fleet-watchdog)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from set_orch.fleet_watchdog import dispatch as wd_dispatch
from set_orch.fleet_watchdog.probe import Finding, fingerprint
from set_orch.fleet_watchdog.store import Store
from set_orch.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SET_WATCHDOG_DIR", str(tmp_path / "wd"))
    monkeypatch.setattr(wd_dispatch, "_projects", lambda: {"set-core"})
    return TestClient(create_app())


def seed(tmp_path, now):
    s = Store(tmp_path / "wd").load()
    s.upsert(Finding("p", "fail", "s1", "p on s1", {"n": 1}, owner_hint="set-core"), now)
    s.save()
    s.append_tick({"at": now, "interval_s": 300})
    return fingerprint("p", "s1")


def test_summary_is_stale_before_any_tick(client):
    data = client.get("/api/fleet/watchdog").json()
    assert data["schema"] == "set-watchdog/1" and data["badge"] == "stale" and data["counts"]["open"] == 0


def test_summary_mute_and_dispatch(client, tmp_path, monkeypatch):
    import time
    fp = seed(tmp_path, time.time())
    data = client.get("/api/fleet/watchdog").json()
    assert data["badge"] == "red" and data["open"][0]["fp"] == fp and data["open"][0]["untriaged"] is True

    asked = []
    monkeypatch.setattr(wd_dispatch, "set_fleet_ask", lambda o, t, s: asked.append(o) or {"ok": True, "engagement": "e"})
    res = client.post(f"/api/fleet/watchdog/{fp}/dispatch").json()
    assert res["ok"] and asked == ["set-core"]
    assert client.post(f"/api/fleet/watchdog/{fp}/dispatch").json()["reason"] == "already dispatched"

    assert client.post(f"/api/fleet/watchdog/{fp}/mute", json={"days": 3}).json()["ok"]
    data = client.get("/api/fleet/watchdog").json()
    assert data["counts"]["open"] == 0 and data["counts"]["muted"] == 1 and data["badge"] == "ok"


def test_bad_fingerprint_and_unknown_finding(client):
    assert client.post("/api/fleet/watchdog/zz/mute", json={"days": 1}).status_code == 400
    assert client.post("/api/fleet/watchdog/0123456789abcdef/mute", json={"days": 1}).status_code == 404
    assert client.post("/api/fleet/watchdog/0123456789abcdef/dispatch").status_code == 404
