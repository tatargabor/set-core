"""set-watchdog — tick, store, probes, triage, dispatch (change `fleet-watchdog`).

Probes are driven with the measured shapes: transcript records with `origin.kind`, the
fleet payload's agent records, the relay's waiting records, `set-doctor/1` records. No
real text is used anywhere — the probes must not need any.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from set_orch.fleet_watchdog import dispatch as wd_dispatch
from set_orch.fleet_watchdog import probes as P
from set_orch.fleet_watchdog import tick as wd_tick
from set_orch.fleet_watchdog import triage as wd_triage
from set_orch.fleet_watchdog import view
from set_orch.fleet_watchdog.probe import PROBE_ERROR, Context, Finding, Probe, fingerprint
from set_orch.fleet_watchdog.store import OPEN, RESOLVED, Store

NOW = 1_800_000_000.0


def cfg(**over):
    store = {"watchdog.enabled": "true"}
    store.update({k.replace("__", "."): v for k, v in over.items()})
    return lambda key, project=None, default=None: store.get(key, default)


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("SET_WATCHDOG_DIR", str(tmp_path / "wd"))
    return tmp_path / "wd"


@pytest.fixture(autouse=True)
def _projects(monkeypatch):
    """Dispatch resolves owners against the registry: never this machine's."""
    monkeypatch.setattr(wd_dispatch, "_projects", lambda: {"set-core", "set-agent-comm", "proj"})


def probe_of(name, *findings, interval=60):
    return Probe(name, interval, lambda ctx: list(findings))


def f(probe="p", subject="s1", severity="warn", **ev):
    return Finding(probe, severity, subject, f"{probe} on {subject}", ev)


def no_triage(*a, **k):
    return 0


def no_dispatch(*a, **k):
    return 0


def run(base, probes, now=NOW, get=None, **kw):
    return wd_tick.tick(base=base, get=get or cfg(), now=now, probes=probes, force=True,
                        triage=kw.get("triage", no_triage), dispatch=kw.get("dispatch", no_dispatch))


# ---- the finding contract -----------------------------------------------------------

def test_fingerprint_is_probe_and_subject_only():
    a = Finding("p", "warn", "s", "one", {"n": 1})
    b = Finding("p", "fail", "s", "two", {"n": 2})
    assert a.fp == b.fp == fingerprint("p", "s")
    assert Finding("p", "warn", "t", "x").fp != a.fp


@pytest.mark.parametrize("evidence", [{"text": "a\nb"}, {"text": "x" * 500}, {"obj": {"a": 1}}])
def test_evidence_must_be_shape_only(evidence):
    with pytest.raises(ValueError):
        Finding("p", "warn", "s", "x", evidence)


# ---- tick, store, lock --------------------------------------------------------------

def test_same_anomaly_on_two_ticks_is_one_finding(base):
    """AC-3."""
    probes = {"p": probe_of("p", f())}
    run(base, probes, now=NOW)
    run(base, probes, now=NOW + 300)
    recs = list(Store(base).load().findings.values())
    assert len(recs) == 1
    assert recs[0]["first_seen"] == NOW and recs[0]["last_seen"] == NOW + 300


def test_anomaly_stops_resolves_and_open_count_drops(base):
    """AC-4."""
    run(base, {"p": probe_of("p", f())}, now=NOW)
    assert view.summary(base, get=cfg(), now=NOW)["counts"]["open"] == 1
    run(base, {"p": probe_of("p")}, now=NOW + 300)
    rec = next(iter(Store(base).load().findings.values()))
    assert rec["state"] == RESOLVED and rec["resolved_at"] == NOW + 300
    assert view.summary(base, get=cfg(), now=NOW + 300)["counts"]["open"] == 0


def test_a_probe_that_did_not_run_resolves_nothing(base):
    run(base, {"p": probe_of("p", f())}, now=NOW)
    run(base, {"q": probe_of("q")}, now=NOW + 300)
    assert next(iter(Store(base).load().findings.values()))["state"] == OPEN


def test_a_probe_raising_is_a_finding_and_the_others_run(base):
    """AC-2."""
    def boom(ctx):
        raise RuntimeError("x")
    line = run(base, {"bad": Probe("bad", 60, boom), "good": probe_of("good", f("good"))})
    recs = {r["probe"]: r for r in Store(base).load().findings.values()}
    assert PROBE_ERROR in recs and recs[PROBE_ERROR]["subject"] == "bad"
    assert "good" in recs and line["ran"] == ["bad", "good"]
    # its error resolves once the probe runs cleanly again
    run(base, {"bad": probe_of("bad")}, now=NOW + 300)
    recs = {r["probe"]: r for r in Store(base).load().findings.values()}
    assert recs[PROBE_ERROR]["state"] == RESOLVED


def test_overlapping_tick_exits_and_changes_nothing(base):
    """AC-1."""
    started, release = threading.Event(), threading.Event()

    def slow(ctx):
        started.set()
        release.wait(5)
        return []
    th = threading.Thread(target=run, args=(base, {"slow": Probe("slow", 60, slow)}))
    th.start()
    assert started.wait(5)
    out = run(base, {"p": probe_of("p", f())})
    release.set()
    th.join(5)
    assert out == {"skipped": "locked", "holder": str(os.getpid())}
    assert not any(r["probe"] == "p" for r in Store(base).load().findings.values())


def test_tick_log_carries_counts_never_evidence(base):
    run(base, {"p": probe_of("p", f(secretish="evidence-value"))})
    text = (base / "ticks.jsonl").read_text()
    assert "evidence-value" not in text and json.loads(text)["new"] == 1
    assert oct(os.stat(base / "findings.json").st_mode)[-3:] == "600"


def test_kill_switch(base):
    assert wd_tick.tick(base=base, get=cfg(watchdog__enabled="false"), probes={}) == {"skipped": "disabled"}
    assert not (base / "ticks.jsonl").exists()


def test_due_respects_interval(base):
    calls = []
    p = Probe("p", 600, lambda ctx: calls.append(ctx.now) or [])
    for t in (NOW, NOW + 300, NOW + 600):
        wd_tick.tick(base=base, get=cfg(), now=t, probes={"p": p}, triage=no_triage, dispatch=no_dispatch)
    assert calls == [NOW, NOW + 600]


def test_muted_recurrence_is_stored_but_not_counted(base):
    """AC-13."""
    run(base, {"p": probe_of("p", f())}, now=NOW)
    fp = fingerprint("p", "s1")
    assert view.mute(fp, 2, base, now=NOW)
    run(base, {"p": probe_of("p", f())}, now=NOW + 300)
    s = view.summary(base, get=cfg(), now=NOW + 300)
    assert s["counts"]["open"] == 0 and s["counts"]["muted"] == 1 and s["muted"][0]["fp"] == fp
    assert s["muted"][0]["muted"] is True


# ---- badge --------------------------------------------------------------------------

def test_badge_stale_is_not_zero(base):
    """AC-12: 40 min old at a 5-min interval."""
    run(base, {"p": probe_of("p")}, now=NOW)
    s = view.summary(base, get=cfg(), now=NOW + 40 * 60)
    assert s["badge"] == "stale" and s["last_tick_at"] == NOW
    assert view.summary(base, get=cfg(), now=NOW + 60)["badge"] == "ok"


def test_badge_never_ticked_is_stale(base):
    assert view.summary(base, get=cfg(), now=NOW)["badge"] == "stale"


def test_badge_red_on_any_fail(base):
    run(base, {"p": probe_of("p", f(), f(subject="s2", severity="fail"))})
    assert view.summary(base, get=cfg(), now=NOW + 1)["badge"] == "red"
    run(base, {"p": probe_of("p", f())}, now=NOW + 2)
    assert view.summary(base, get=cfg(), now=NOW + 3)["badge"] == "count"


# ---- wake-storm ---------------------------------------------------------------------

def iso(t):
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def rec_human(t):
    return {"type": "user", "timestamp": iso(t), "origin": {"kind": "human"}, "message": {"content": "x"}}


def rec_bus_task(t):
    return {"type": "user", "timestamp": iso(t), "origin": {"kind": "task-notification", "producer": "session-task"},
            "message": {"content": '<task-notification> <summary>Background command "agent-comm inbox" completed'}}


def rec_own_task(t):
    return {"type": "user", "timestamp": iso(t), "origin": {"kind": "task-notification"},
            "message": {"content": '<task-notification> <summary>Background command "Run tests" completed'}}


def rec_bus_stop(t):
    return {"type": "user", "timestamp": iso(t), "isMeta": True,
            "message": {"content": [{"type": "text", "text": "Stop hook feedback: [set-agent-comm] mail"}]}}


def rec_tool(t):
    return {"type": "user", "timestamp": iso(t), "toolUseResult": {}, "message": {"content": [{"type": "tool_result"}]}}


def test_classify_turn_starts_by_measured_markers():
    assert P.classify_turn_start(rec_human(NOW)) == "human"
    assert P.classify_turn_start(rec_bus_task(NOW)) == "bus"
    assert P.classify_turn_start(rec_own_task(NOW)) == "own-task"
    assert P.classify_turn_start(rec_bus_stop(NOW)) == "bus"
    assert P.classify_turn_start(rec_tool(NOW)) is None
    skill = {"type": "user", "isMeta": True, "message": {"content": [{"type": "text", "text": "Base directory for this skill"}]}}
    assert P.classify_turn_start(skill) is None
    other_stop = {"type": "user", "isMeta": True, "message": {"content": "Stop hook feedback:\nThe user is away"}}
    assert P.classify_turn_start(other_stop) == "hook"
    clear = {"type": "user", "rowSource": "local", "message": {"content": "<command-name>/clear</command-name>"}}
    assert P.classify_turn_start(clear) == "command"


def test_wakes_after_a_human_prompt_only_count():
    recs = [rec_bus_task(NOW - 3000), rec_human(NOW - 2500), rec_bus_task(NOW - 2000),
            rec_bus_stop(NOW - 1000), rec_own_task(NOW - 900), rec_tool(NOW - 800)]
    c = P.count_wakes(recs, NOW, 7200)
    assert c["bus"] == 2 and c["own-task"] == 1 and c["human"] == 1


def _payload(tmp_path, records, **agent):
    cwd = str(tmp_path / "proj")
    tp = P.transcript_path(cwd, "sess-1", home=str(tmp_path))
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text("".join(json.dumps(r) + "\n" for r in records))
    a = {"kind": "interactive", "session_id": "sess-1", "cwd": cwd, "project_root": cwd, "project": "proj",
         "seat": "proj#sess", "context": {"tokens": 1000}}
    a.update(agent)
    return {"projects": [{"name": "proj", "agents": [a]}], "owner_reachable": True, "bus_reachable": True}


def ctx_with(payload, engagements=None, now=NOW, get=None):
    c = Context(now=now, get=get or cfg())
    c.cache["fleet"] = (True, payload)
    c.cache["engagements"] = (True, engagements or {"engagements": []})
    return c


def test_wake_storm_reports_an_idle_session(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    recs = [rec_human(NOW - 7000)] + [rec_bus_task(NOW - 600 * i) for i in range(1, 4)]
    out = P.probe_wake_storm(ctx_with(_payload(tmp_path, recs, last_human_input_seconds=7000)))
    assert len(out) == 1 and out[0].subject == "session:sess-1" and out[0].evidence["bus_wakes"] == 3


def test_wake_storm_quiet_while_a_person_is_working_with_the_session(tmp_path, monkeypatch):
    """Measured live 2026-11-24: 3 bus wakes 25 min after a typed prompt is a conversation."""
    monkeypatch.setenv("HOME", str(tmp_path))
    recs = [rec_human(NOW - 1600)] + [rec_bus_task(NOW - 400 * i) for i in range(1, 4)]
    assert P.probe_wake_storm(ctx_with(_payload(tmp_path, recs, last_human_input_seconds=1550))) == []


def test_wake_storm_quiet_when_the_session_has_an_open_request(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    recs = [rec_bus_task(NOW - 600 * i) for i in range(1, 5)]
    eng = {"engagements": [{"asker": "proj#sess", "state": "open"}]}
    assert P.probe_wake_storm(ctx_with(_payload(tmp_path, recs), eng)) == []


def test_wake_storm_warns_when_no_marker_is_recognised(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    recs = [{"type": "user", "timestamp": iso(NOW - 60 * i), "message": {"content": "x"}} for i in range(1, 4)]
    out = P.probe_wake_storm(ctx_with(_payload(tmp_path, recs)))
    assert [x.subject for x in out] == ["classifier"]
    # one unknown start in a fresh session is not a claim about the classifier
    assert P.probe_wake_storm(ctx_with(_payload(tmp_path, recs[:1]))) == []


def test_payload_probes_never_go_silent_when_the_payload_is_gone():
    """AC-6 (half): every payload-reading probe says it could not measure."""
    c = Context(now=NOW, get=cfg())
    c.cache["fleet"] = (False, "URLError")
    for probe in (P.probe_wake_storm, P.probe_auto_clear_miss):
        out = probe(c)
        assert len(out) == 1 and out[0].severity == "warn" and out[0].subject == "source:fleet payload"


def test_service_health_fails_set_web_when_payload_is_gone(monkeypatch):
    """AC-6 (other half)."""
    c = Context(now=NOW, get=cfg())
    c.cache["fleet"] = (False, "URLError")
    monkeypatch.setattr(P, "_systemctl", lambda *a: subprocess.CompletedProcess(a, 0, "", ""))
    monkeypatch.setattr(P, "_registry", lambda get: {})
    out = P.probe_service_health(c)
    assert [(x.subject, x.severity) for x in out] == [("unit:set-web", "fail")]


def test_unit_owner_from_the_execstart_path(tmp_path):
    units = tmp_path / ".config" / "systemd" / "user"
    units.mkdir(parents=True)
    (tmp_path / "code" / "proj" / "scripts").mkdir(parents=True)
    (units / "x.service").write_text("[Service]\nExecStart=/usr/bin/python3 %h/code/proj/scripts/run.py\n")
    reg = {"proj": {"path": str(tmp_path / "code" / "proj")}, "other": {"path": str(tmp_path / "code" / "o")}}
    assert P.unit_owner("x.service", reg, home=str(tmp_path)) == "proj"
    assert P.unit_owner("missing.service", reg, home=str(tmp_path)) is None


def test_service_health_reports_failed_units(monkeypatch):
    c = ctx_with({"projects": [], "owner_reachable": False, "bus_reachable": True})
    monkeypatch.setattr(P, "_systemctl", lambda *a: subprocess.CompletedProcess(
        a, 0, "mail-sync.service loaded failed failed Mail\n", ""))
    monkeypatch.setattr(P, "_registry", lambda get: {})
    subjects = {x.subject for x in P.probe_service_health(c)}
    assert subjects == {"unit:set-agent-owner", "unit:mail-sync.service"}


def test_a_failed_unit_carries_its_result_and_exit_status(monkeypatch):
    """AC-18 (B-221): the triage can name the cause only if the evidence carries it."""
    c = ctx_with({"projects": [], "owner_reachable": True, "bus_reachable": True})

    def systemctl(*a):
        out = "Result=timeout\nExecMainStatus=15\n" if a[0] == "show" else "mail-sync.service loaded failed failed Mail\n"
        return subprocess.CompletedProcess(a, 0, out, "")
    monkeypatch.setattr(P, "_systemctl", systemctl)
    monkeypatch.setattr(P, "_registry", lambda get: {})
    [unit] = [x for x in P.probe_service_health(c) if x.subject == "unit:mail-sync.service"]
    assert unit.evidence["result"] == "timeout" and unit.evidence["exit_status"] == 15


# ---- auto-clear-miss ----------------------------------------------------------------

def test_auto_clear_miss_after_the_grace(tmp_path, monkeypatch):
    """AC-5: above the threshold for 20 min, no clear (same session id)."""
    payload = _payload(tmp_path, [], context={"tokens": 460_000})
    monkeypatch.setattr(P, "threshold_for", lambda tree, home, reg: (400_000, "package"))
    monkeypatch.setattr(P, "_registry", lambda get: {})
    states = {}
    first = P.probe_auto_clear_miss(Context(now=NOW, get=cfg(), cache={"fleet": (True, payload)}, states=states))
    assert first == []
    later = P.probe_auto_clear_miss(Context(now=NOW + 20 * 60, get=cfg(), cache={"fleet": (True, payload)},
                                            states=states))
    assert len(later) == 1 and later[0].severity == "fail"
    assert later[0].evidence["tokens"] == 460_000 and later[0].evidence["threshold"] == 400_000
    assert later[0].evidence["minutes_above"] == 20


def test_auto_clear_miss_forgets_a_cleared_session(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "threshold_for", lambda tree, home, reg: (400_000, "package"))
    monkeypatch.setattr(P, "_registry", lambda get: {})
    states = {}
    hot = _payload(tmp_path, [], context={"tokens": 460_000})
    P.probe_auto_clear_miss(Context(now=NOW, get=cfg(), cache={"fleet": (True, hot)}, states=states))
    cleared = _payload(tmp_path, [], session_id="sess-2", context={"tokens": 20_000})
    P.probe_auto_clear_miss(Context(now=NOW + 60, get=cfg(), cache={"fleet": (True, cleared)}, states=states))
    assert states["auto-clear-miss"]["crossed"] == {}


def test_auto_clear_threshold_from_the_unit_flag(tmp_path, monkeypatch):
    from set_doctor import auto_clear as ac
    monkeypatch.setattr(ac, "watcher_units", lambda home, tree: [("x.service", "/bin/bash w.sh --threshold 300000")])
    assert P.threshold_for("/t", "/h", {}) == (300000, "unit")
    monkeypatch.setattr(ac, "watcher_units", lambda home, tree: [])
    assert P.threshold_for("/t", "/h", {}) == (None, "no-unit")


# ---- relay-hold ---------------------------------------------------------------------

def test_relay_hold_ignores_continuations(monkeypatch):
    from set_orch.fleet import question_relay as qr
    monkeypatch.setattr(qr, "list_waiting", lambda: [
        {"session_id": "a", "started": NOW - 3600, "kind": None, "questions": 1},
        {"session_id": "b", "started": NOW - 3600, "kind": "continuation"},
        {"session_id": "c", "started": NOW - 60, "kind": None}])
    out = P.probe_relay_hold(Context(now=NOW, get=cfg()))
    # No cwd: the terminal input cannot be measured, so the hold is still shown (B-222).
    assert [x.subject for x in out] == ["session:a"] and out[0].evidence["minutes"] == 60
    assert out[0].evidence["typed_in_terminal"] is None


def _iso(t):
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _held(tmp_path, monkeypatch, queued):
    """One ask held 40 min in /w/proj, whose transcript carries `queued` (offset s, content)."""
    from set_orch.fleet import question_relay as qr
    started = NOW - 40 * 60
    monkeypatch.setattr(qr, "list_waiting", lambda: [
        {"session_id": "s1", "started": started, "questions": 2, "cwd": "/w/proj"}])
    path = P.transcript_path("/w/proj", "s1", home=str(tmp_path))
    path.parent.mkdir(parents=True)
    rows = [{"type": "user", "timestamp": _iso(started - 5), "message": {"content": "earlier"}}]
    rows += [{"type": "queue-operation", "operation": "enqueue", "timestamp": _iso(started + off), "content": c}
             for off, c in queued]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return P.probe_relay_hold(Context(now=NOW, get=cfg()), home=str(tmp_path))


def test_relay_hold_with_nothing_typed_is_the_owner_not_a_defect(tmp_path, monkeypatch):
    """AC-16 (B-222): a harness notification queued, or a prompt typed BEFORE the hold, is not B-214."""
    assert _held(tmp_path, monkeypatch, [(60, "<task-notification>x</task-notification>"),
                                          (-30, "typed before the hold")]) == []


def test_relay_hold_with_a_prompt_typed_into_the_terminal_is_reported(tmp_path, monkeypatch):
    """AC-17 (B-214's symptom, measured on a real session)."""
    out = _held(tmp_path, monkeypatch, [(120, "/dd"), (300, "<task-notification>x</task-notification>")])
    assert [x.subject for x in out] == ["session:s1"]
    assert out[0].evidence["typed_in_terminal"] == 1 and out[0].evidence["minutes"] == 40
    assert "typed in its terminal" in out[0].summary


# ---- doctor-delta -------------------------------------------------------------------

def test_doctor_delta_baseline_then_new_fail():
    """AC-7: a module doctor starts returning a fail → one finding with module + project."""
    states = {}
    old = {"status": "fail", "module": "m", "project": "a", "section": "project", "name": "x"}
    new = {"status": "fail", "module": "m", "project": "b", "section": "project", "name": "x"}
    c = lambda: Context(now=NOW, get=cfg(), states=states)
    assert P.probe_doctor_delta(c(), fetch=lambda: [old]) == []
    out = P.probe_doctor_delta(c(), fetch=lambda: [old, new])
    assert len(out) == 1 and out[0].evidence["module"] == "m" and out[0].evidence["project"] == "b"
    assert out[0].owner_hint == "m"


def test_doctor_delta_unreadable_is_a_warn():
    def broken():
        raise ValueError("bad json")
    out = P.probe_doctor_delta(Context(now=NOW, get=cfg()), fetch=broken)
    assert out[0].severity == "warn"


# ---- triage -------------------------------------------------------------------------

def _store_with(base, *findings, now=NOW):
    s = Store(base).load()
    for x in findings:
        s.upsert(x, now)
    return s


def test_triage_prompt_holds_only_shape_fields(base):
    s = _store_with(base, f(n=3))
    seen = {}

    def runner(prompt):
        seen["p"] = prompt
        return json.dumps({"findings": [{"fp": fingerprint("p", "s1"), "verdict": "real", "owner": "set-core",
                                          "brief": "b"}]})
    assert wd_triage.triage_new(s, [fingerprint("p", "s1")], now=NOW, get=cfg(), runner=runner, registry={}) == 1
    block = seen["p"].split("FINDINGS:")[1]
    sent = json.loads(block)
    assert set(sent[0]) == set(wd_triage.PROMPT_FIELDS)
    assert s.findings[fingerprint("p", "s1")]["triage"]["verdict"] == "real"


def test_triage_budget_exhausted_stays_untriaged(base):
    """AC-8."""
    s = _store_with(base, f())
    for _ in range(2):
        s.bump(wd_triage.COUNTER, NOW)
    called = []
    n = wd_triage.triage_new(s, [fingerprint("p", "s1")], now=NOW, get=cfg(watchdog__triage_daily_calls=2),
                             runner=lambda p: called.append(p), registry={})
    assert n == 0 and called == [] and s.findings[fingerprint("p", "s1")]["triage"] is None


@pytest.mark.parametrize("answer", [None, "", "not json", '{"findings": [{"fp": "x", "verdict": "maybe"}]}'])
def test_triage_bad_answer_is_untriaged_never_noise(base, answer):
    s = _store_with(base, f())
    wd_triage.triage_new(s, [fingerprint("p", "s1")], now=NOW, get=cfg(), runner=lambda p: answer, registry={})
    assert s.findings[fingerprint("p", "s1")]["triage"] is None


def test_triage_known_is_recorded_and_not_dispatched(base):
    """AC-9."""
    fp = fingerprint("relay-hold", "session:a")
    s = _store_with(base, Finding("relay-hold", "warn", "session:a", "held", {"minutes": 40}))
    wd_triage.triage_new(s, [fp], now=NOW, get=cfg(), registry={},
                         runner=lambda p: json.dumps({"findings": [{"fp": fp, "verdict": "known:B-214",
                                                                     "owner": "set-core", "brief": ""}]}))
    assert s.findings[fp]["triage"]["verdict"] == "known:B-214"
    asked = []
    assert wd_dispatch.dispatch_ready(s, now=NOW, get=cfg(), asker=lambda *a: asked.append(a)) == 0 and asked == []


def test_a_brief_written_for_another_finding_leaves_it_untriaged(base):
    """AC-19 (B-221): the measured swap: each unit's brief opens with the other unit."""
    a = Finding("service-health", "fail", "unit:alpha-stats.service", "failed", {"unit": "alpha-stats.service"})
    b = Finding("service-health", "fail", "unit:beta-videos.service", "failed", {"unit": "beta-videos.service"})
    c = Finding("service-health", "fail", "unit:gamma.service", "failed", {"unit": "gamma.service"})
    s = _store_with(base, a, b, c)
    answer = {"findings": [
        {"fp": a.fp, "verdict": "real", "owner": "proj",
         "brief": "unit beta-videos.service is failed. Companion unit alpha-stats.service failed too."},
        {"fp": b.fp, "verdict": "real", "owner": "proj", "brief": "unit alpha-stats is failed; check it."},
        {"fp": c.fp, "verdict": "real", "owner": "proj",
         "brief": "gamma.service is failed; beta-videos.service failed at the same time."}]}
    n = wd_triage.triage_new(s, [a.fp, b.fp, c.fp], now=NOW, get=cfg(), registry={},
                             runner=lambda p: json.dumps(answer))
    assert n == 1
    assert s.findings[a.fp]["triage"] is None and s.findings[b.fp]["triage"] is None
    assert s.findings[c.fp]["triage"]["verdict"] == "real"


def test_a_brief_naming_no_subject_is_accepted():
    rec = {"fp": "1", "subject": "session:0d56fb05-5e5c-49fe-9501-8e8781585b97"}
    other = {"fp": "2", "subject": "unit:x.service"}
    assert wd_triage.brief_names_another("a held question; check the relay log", rec, [rec, other]) is None
    assert wd_triage.brief_names_another("session 0d56fb05 holds; x.service too", rec, [rec, other]) is None
    assert wd_triage.brief_names_another("x.service failed", rec, [rec, other]) is other


def test_register_titles_reads_only_the_open_section(tmp_path):
    reg = tmp_path / "openspec" / "bugs"
    reg.mkdir(parents=True)
    (reg / "README.md").write_text("# x\n## Open\n\n### B-2 — two\n- body\n### B-1 — one\n## Closed\n### B-0 — zero\n")
    assert wd_triage.register_titles(str(tmp_path)) == ["B-2 — two", "B-1 — one"]


def test_run_glm_contract(tmp_path, monkeypatch):
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "set-glm").write_text("#!/bin/sh\necho \"$@\" > " + str(tmp_path / "args") +
                                  "\ncat > /dev/null\necho '{\"result\": \"{\\\"findings\\\": []}\"}'\n")
    (fake / "set-glm").chmod(0o755)
    monkeypatch.setenv("PATH", str(fake) + os.pathsep + os.environ["PATH"])
    assert wd_triage.run_glm("prompt") == '{"findings": []}'
    args = (tmp_path / "args").read_text()
    assert "-p" in args and "disableAllHooks" in args and "--no-session-persistence" in args


# ---- dispatch -----------------------------------------------------------------------

def _real(s, fp, owner="set-agent-comm"):
    s.findings[fp]["triage"] = {"verdict": "real", "owner": owner, "brief": "fix it", "at": NOW}


def test_auto_dispatch_sends_one_request(base):
    """AC-10."""
    s = _store_with(base, f())
    fp = fingerprint("p", "s1")
    _real(s, fp)
    asked = []
    n = wd_dispatch.dispatch_ready(s, now=NOW, get=cfg(),
                                   asker=lambda o, t, subj: asked.append((o, t, subj)) or {"ok": True, "engagement": "e1"})
    assert n == 1 and asked[0][0] == "set-agent-comm"
    assert "may NOT deploy" in asked[0][1] and fp in asked[0][1]
    assert s.findings[fp]["dispatch"]["state"] == "dispatched" and s.findings[fp]["dispatch"]["engagement"] == "e1"
    # one open dispatch per fingerprint
    assert wd_dispatch.dispatch_ready(s, now=NOW + 300, get=cfg(), asker=lambda *a: asked.append(a)) == 0
    assert len(asked) == 1


def test_daily_cap_holds_and_dispatch_now_is_offered(base):
    """AC-11."""
    s = _store_with(base, f())
    fp = fingerprint("p", "s1")
    _real(s, fp)
    for _ in range(3):
        s.bump(wd_dispatch.COUNTER, NOW)
    asked = []
    assert wd_dispatch.dispatch_ready(s, now=NOW, get=cfg(), asker=lambda *a: asked.append(a)) == 0
    assert s.findings[fp]["dispatch"] == {"state": "held", "reason": "daily cap"} and asked == []
    res = wd_dispatch.dispatch_now(s, fp, now=NOW, asker=lambda *a: {"ok": True, "engagement": "e2"})
    assert res["ok"] and s.findings[fp]["dispatch"]["state"] == "dispatched"


@pytest.mark.parametrize("mode_, state", [("propose", "proposed"), ("notify", None), ("off", None)])
def test_modes_other_than_auto_send_nothing(base, mode_, state):
    s = _store_with(base, f())
    fp = fingerprint("p", "s1")
    _real(s, fp)
    asked = []
    wd_dispatch.dispatch_ready(s, now=NOW, get=cfg(watchdog__remediation=mode_), asker=lambda *a: asked.append(a))
    assert asked == [] and (s.findings[fp].get("dispatch") or {}).get("state") == state


def test_cooldown_after_a_reopen(base):
    s = _store_with(base, f())
    fp = fingerprint("p", "s1")
    _real(s, fp)
    wd_dispatch.dispatch_ready(s, now=NOW, get=cfg(), asker=lambda *a: {"ok": True})
    s.resolve_absent("p", set(), NOW + 600)
    s.upsert(f(), NOW + 1200)                  # it came back
    _real(s, fp)
    asked = []
    wd_dispatch.dispatch_ready(s, now=NOW + 1200, get=cfg(), asker=lambda *a: asked.append(a))
    assert asked == [] and s.findings[fp]["dispatch"]["reason"] == "cooldown"
    wd_dispatch.dispatch_ready(s, now=NOW + 25 * 3600, get=cfg(), asker=lambda *a: asked.append(a) or {"ok": True})
    assert len(asked) == 1


def test_set_fleet_ask_carrier_passes_no_provider_and_its_own_seat(tmp_path, monkeypatch):
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "set-fleet-ask").write_text("#!/bin/sh\necho \"$SET_AGENT_NAME|$CLAUDE_CODE_SESSION_ID|$@\" > "
                                        + str(tmp_path / "args") + "\necho 'sent (engagement eng-7)'\n")
    (fake / "set-fleet-ask").chmod(0o755)
    monkeypatch.setenv("PATH", str(fake) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    res = wd_dispatch.set_fleet_ask("set-agent-comm", "brief", "watchdog: p")
    args = (tmp_path / "args").read_text()
    assert res == {"ok": True, "engagement": "eng-7"}
    assert args.startswith("set-watchdog||set-agent-comm brief --subject watchdog: p --from set-watchdog")
    assert "provider" not in args and "glm" not in args.lower()


def test_dispatch_failure_is_recorded(base):
    s = _store_with(base, f())
    fp = fingerprint("p", "s1")
    _real(s, fp)
    wd_dispatch.dispatch_ready(s, now=NOW, get=cfg(), asker=lambda *a: {"ok": False, "reason": "no seat"})
    assert s.findings[fp]["dispatch"]["state"] == "failed" and s.counter(wd_dispatch.COUNTER, NOW) == 0


# ---- the tick wires triage and dispatch ---------------------------------------------

def test_tick_triages_only_when_something_opened(base):
    calls = []
    probes = {"p": probe_of("p", f())}
    run(base, probes, now=NOW, triage=lambda store, fps, **k: calls.append(list(fps)) or 0)
    run(base, probes, now=NOW + 300, triage=lambda store, fps, **k: calls.append(list(fps)) or 0)
    assert calls == [[fingerprint("p", "s1")]]


def test_a_measured_owner_hint_outranks_the_model():
    rec = {"owner_hint": "proj", "triage": {"owner": "set-core"}}
    assert wd_dispatch.owner_of(rec) == "proj"
    # a hint that is not a project (a module name) leaves the choice to the model
    assert wd_dispatch.owner_of({"owner_hint": "some-module", "triage": {"owner": "set-core"}}) == "set-core"
    # the model naming no registered project is no owner at all
    assert wd_dispatch.owner_of({"triage": {"owner": "made-up"}}) is None
