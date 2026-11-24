"""set-doctor's `watchdog` record (fleet-watchdog, AC-14/AC-15): measured from the tick log."""

from __future__ import annotations

import json

import pytest

from set_doctor import checks as ck

NOW = 1_800_000_000.0


def ctx_at(tmp_path):
    return ck.Context(root=str(tmp_path), home=str(tmp_path), env={"PATH": "/usr/bin"})


def install_timer(tmp_path):
    units = tmp_path / ".config" / "systemd" / "user"
    units.mkdir(parents=True)
    (units / "set-watchdog.timer").write_text("[Timer]\n")


def write_tick(tmp_path, at, interval=300):
    d = tmp_path / ".local" / "share" / "set-core" / "watchdog"
    d.mkdir(parents=True)
    (d / "ticks.jsonl").write_text(json.dumps({"at": at, "interval_s": interval, "open": 2}) + "\n")


@pytest.fixture
def active(monkeypatch):
    monkeypatch.setattr(ck, "run", lambda cmd, **k: (0, "active\n", ""))


def test_not_installed_is_warn_with_the_install_command(tmp_path):
    """AC-15."""
    c = ck.check_watchdog(ctx_at(tmp_path), now=NOW)
    assert (c.section, c.name, c.status) == ("fleet", "watchdog", "warn") and "install" in c.fix


def test_stale_tick_is_fail_naming_the_time(tmp_path, active):
    """AC-14: enabled, last tick two hours old at a 5-min interval."""
    install_timer(tmp_path)
    write_tick(tmp_path, NOW - 7200)
    c = ck.check_watchdog(ctx_at(tmp_path), now=NOW)
    assert c.status == "fail" and "120 min ago" in c.detail


def test_fresh_tick_is_ok(tmp_path, active):
    install_timer(tmp_path)
    write_tick(tmp_path, NOW - 120)
    assert ck.check_watchdog(ctx_at(tmp_path), now=NOW).status == "ok"


def test_never_ticked_is_fail(tmp_path, active):
    install_timer(tmp_path)
    assert ck.check_watchdog(ctx_at(tmp_path), now=NOW).status == "fail"


def test_inactive_timer_is_fail(tmp_path, monkeypatch):
    install_timer(tmp_path)
    monkeypatch.setattr(ck, "run", lambda cmd, **k: (3, "inactive\n", ""))
    c = ck.check_watchdog(ctx_at(tmp_path), now=NOW)
    assert c.status == "fail" and "enable --now" in c.fix
