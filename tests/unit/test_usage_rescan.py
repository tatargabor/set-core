"""Rescanning the browser's Claude sessions from the dashboard.

The store tests pin what happens to the FILE (manual entries kept, scanned ones replaced, 0600,
no write on an empty scan). The route tests pin the answer (names, a fresh snapshot, no cookie)
and the refusal of a second concurrent rescan. The keyring test drives the lookup script in a
fake `gi` whose collection walk raises on a dangling item, which is the failure measured live.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient

import set_orch.api.usage as usage_api
from set_orch.usage import chrome_scan

FRESH = "sk-fresh-cookie-value"
STALE = "sk-stale-cookie-value"
MANUAL = "sk-manual-cookie-value"


def _store(tmp_path, entries):
    path = tmp_path / "claude-session.json"
    path.write_text(json.dumps({"accounts": entries}))
    os.chmod(path, 0o664)
    return path


def _scan_returning(results):
    def scan(force_refresh, existing_accounts):
        assert force_refresh is True
        return results
    return scan


def test_fresh_cookies_replace_expired_ones_and_the_file_is_owner_only(tmp_path):
    # AC-8
    path = _store(tmp_path, [
        {"name": "a@example.invalid", "sessionKey": STALE, "source": "chrome-scan"},
        {"name": "hand@example.invalid", "sessionKey": MANUAL, "source": "manual"},
    ])
    out = chrome_scan.rescan(tmp_path, scan=_scan_returning([
        {"name": "a@example.invalid", "sessionKey": FRESH, "source": "chrome-scan"},
    ]))
    assert out == {"found": ["a@example.invalid"], "written": True, "reason": None}
    entries = json.loads(path.read_text())["accounts"]
    assert {(e["name"], e["sessionKey"]) for e in entries} == {
        ("a@example.invalid", FRESH), ("hand@example.invalid", MANUAL)}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_an_empty_or_impossible_scan_writes_nothing(tmp_path):
    # AC-7
    path = _store(tmp_path, [{"name": "a@example.invalid", "sessionKey": STALE, "source": "chrome-scan"}])
    before = path.read_bytes()
    out = chrome_scan.rescan(tmp_path, scan=_scan_returning([]))
    assert out["written"] is False and out["found"] == [] and out["reason"]

    def no_dep(force_refresh, existing_accounts):
        raise ImportError("pycookiecheat")
    out = chrome_scan.rescan(tmp_path, scan=no_dep)
    assert out["written"] is False and "pycookiecheat" in out["reason"]
    assert path.read_bytes() == before


def test_a_second_rescan_while_one_runs_is_refused(tmp_path):
    started, release = threading.Event(), threading.Event()

    def slow(force_refresh, existing_accounts):
        started.set()
        release.wait(5)
        return []

    t = threading.Thread(target=chrome_scan.rescan, args=(tmp_path,), kwargs={"scan": slow})
    t.start()
    assert started.wait(5)
    try:
        try:
            chrome_scan.rescan(tmp_path, scan=_scan_returning([]))
        except chrome_scan.RescanBusy:
            pass
        else:
            raise AssertionError("a concurrent rescan was not refused")
    finally:
        release.set()
        t.join(5)


class _Poller:
    def __init__(self):
        self.refreshed = 0

    def refresh(self):
        self.refreshed += 1

    def snapshot(self):
        return {"accounts": [{"name": "a@example.invalid", "kind": "web", "outcome": "measured",
                              "active": False, "windows": []}],
                "measured_at": "2026-11-08T09:00:00+00:00", "interval_seconds": 60, "last_error": None}


def _client(poller):
    app = FastAPI()
    app.include_router(usage_api.router)
    app.state.usage_poller = poller
    return TestClient(app)


def test_the_route_names_what_it_found_measures_again_and_carries_no_cookie(monkeypatch, tmp_path):
    # AC-9, AC-6 (the measurement is taken at once, not on the next poll)
    _store(tmp_path, [])
    monkeypatch.setenv("WT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(chrome_scan, "scan_chrome_sessions", _scan_returning([
        {"name": "a@example.invalid", "sessionKey": FRESH, "source": "chrome-scan"},
        {"name": "b@example.invalid", "sessionKey": FRESH + "2", "source": "chrome-scan"},
    ]))
    poller = _Poller()
    r = _client(poller).post("/api/usage/accounts/rescan")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] == ["a@example.invalid", "b@example.invalid"]
    assert poller.refreshed == 1 and body["snapshot"]["measured_at"]
    assert FRESH not in r.text


def test_the_route_does_not_measure_after_a_scan_that_wrote_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("WT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(chrome_scan, "scan_chrome_sessions", _scan_returning([]))
    poller = _Poller()
    body = _client(poller).post("/api/usage/accounts/rescan").json()
    assert body["written"] is False and body["reason"] and poller.refreshed == 0


def test_the_route_answers_409_while_busy(monkeypatch):
    def busy(*a, **k):
        raise chrome_scan.RescanBusy("busy")
    monkeypatch.setattr(usage_api, "rescan", busy)
    assert _client(_Poller()).post("/api/usage/accounts/rescan").status_code == 409


FAKE_GI = textwrap.dedent('''
    import sys, types
    class _Err(Exception): pass
    class _Item:
        def __init__(self, label, app, broken=False): self.label, self.app, self.broken = label, app, broken
        def get_label(self):
            if self.broken: raise _Err("No such secret item at path")
            return self.label
        def get_attributes(self): return {"application": self.app}
        def load_secret_sync(self): pass
        def get_secret(self): return types.SimpleNamespace(get_text=lambda: "walked-password")
    class _Collection:
        def get_items(self): return [_Item("x", "y", broken=True), _Item("Chrome Safe Storage", "chrome")]
    class _Service:
        @staticmethod
        def get_sync(flags): return types.SimpleNamespace(get_collections=lambda: [_Collection()])
    MODE = "{mode}"
    def lookup(schema, attrs, cancellable):
        if MODE == "lookup": return "looked-up-password"
        raise _Err("lookup unavailable")
    Secret = types.SimpleNamespace(
        Schema=types.SimpleNamespace(new=lambda *a: object()),
        SchemaFlags=types.SimpleNamespace(DONT_MATCH_NAME=2),
        SchemaAttributeType=types.SimpleNamespace(STRING=0),
        ServiceFlags=types.SimpleNamespace(LOAD_COLLECTIONS=1),
        password_lookup_sync=lookup, Service=_Service)
    gi = types.ModuleType("gi"); gi.require_version = lambda *a: None
    repo = types.ModuleType("gi.repository"); repo.Secret = Secret
    sys.modules["gi"] = gi; sys.modules["gi.repository"] = repo
''')


def _run_keyring_script(mode):
    code = FAKE_GI.replace("{mode}", mode) + chrome_scan._KEYRING_SCRIPT
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)


def test_the_password_is_found_by_attribute_first():
    # AC-10
    r = _run_keyring_script("lookup")
    assert r.stdout.strip() == "looked-up-password", r.stderr


def test_a_dangling_item_does_not_end_the_walk():
    # AC-10: the walk skips the item the secret service cannot load and still finds Chrome's.
    r = _run_keyring_script("walk")
    assert r.stdout.strip() == "walked-password", r.stderr
