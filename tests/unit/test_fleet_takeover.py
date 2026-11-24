"""The takeover watch: a request whose desk stopped moving is interrupted, then replaced.

The decision table is the contract (fleet-engagement-takeover specs). The two failure
directions both cost something real: acting on a working desk burns tokens and kills work;
not acting on a hung one stops the request for good — measured for three hours on 2026-11-24.
"""

from __future__ import annotations

import pytest

from set_orch.fleet import engagement as eng_mod
from set_orch.fleet import mandate_delivery
from set_orch.fleet import takeover as tk
from set_orch.fleet.desk import Desk
from set_orch.fleet.mandate import MandateStore

B = tk.Bounds(stall_seconds=300.0, ceiling_seconds=1800.0, cpu_percent=5.0, max_handovers=2)
NOW = 10_000.0


def eng(**over):
    record = {"id": "e-1", "state": "open", "sent_at": NOW - 600, "opened_at": NOW - 610,
              "nudged_at": None, "handovers": 0, "room": "dm-a--b", "ts": "2026-11-24T08:04:53.868+01:00",
              "asker": "alpha#aaaaaaaa", "project": "beta", "desk_label": "beta-desk",
              "desk_seat": "beta#0000dddd", "desk_mandate": "m-old"}
    record.update(over)
    return record


def row(**over):
    r = {"terminal_label": "beta-desk", "pid": 42, "unit": "set-agent-beta-desk.scope",
         "seat": "beta#0000dddd", "session_id": "sess-old", "state": "working",
         "last_movement_seconds": 2775.0,
         "mandate": {"id": "m-old", "kind": "desk", "project": "beta", "ended": None}}
    r.update(over)
    return r


def decide(e, r, cpu=1.7, asking=0, now=NOW):
    return tk.decide(e, r, cpu_percent=cpu, asking=asking, now=now, b=B)


# -- the stall test --------------------------------------------------------------------


def test_a_hung_tool_call_is_stalled_and_interrupted():
    assert decide(eng(), row()) == (tk.INTERRUPT, "stalled (movement+cpu)")


def test_a_long_test_run_with_background_cpu_is_left_alone():
    assert decide(eng(), row(), cpu=180.0) == (tk.NONE, "working")


def test_unmeasured_cpu_decides_on_movement_alone_and_says_so():
    assert decide(eng(), row(), cpu=None) == (tk.INTERRUPT, "stalled (movement-only)")


def test_a_first_cpu_sample_defers_the_stall_decision_one_round():
    """After a service restart every desk is unsampled; a quiet transcript alone must not
    interrupt what may be a long test run."""
    assert decide(eng(), row(), cpu=tk.PENDING) == (tk.NONE, "cpu-sampling")
    assert decide(eng(sent_at=NOW - 9999), row(), cpu=tk.PENDING)[0] == tk.NONE


def test_a_gone_desk_needs_no_cpu_sample():
    assert decide(eng(), None, cpu=tk.PENDING)[0] == tk.REPLACE


@pytest.mark.parametrize("moved", [10.0, 299.0, 300.0])
def test_a_moving_desk_is_left_alone(moved):
    assert decide(eng(), row(last_movement_seconds=moved))[0] == tk.NONE


@pytest.mark.parametrize("moved", [None, True, "4000"])
def test_unmeasured_movement_is_not_a_stall(moved):
    assert decide(eng(), row(last_movement_seconds=moved))[0] == tk.NONE


def test_a_desk_asking_the_owner_is_never_interrupted():
    assert decide(eng(sent_at=NOW - 9999), row(state="asking")) == (tk.NONE, "desk-asking-owner")


def test_a_desk_waiting_on_its_own_request_is_left_to_that_request_s_watch():
    assert decide(eng(), row(), asking=1) == (tk.NONE, "desk-waiting-on-its-own-request")


# -- the ladder ------------------------------------------------------------------------


def test_past_the_ceiling_a_moving_desk_is_interrupted_once():
    assert decide(eng(sent_at=NOW - 1900), row(last_movement_seconds=5)) == (tk.INTERRUPT, "past-ceiling")
    after = eng(sent_at=NOW - 1900, nudged_at=NOW - 60)
    assert decide(after, row(last_movement_seconds=5))[0] == tk.NONE
    assert decide(after, row(last_movement_seconds=5), now=NOW + 3600)[0] == tk.NONE


def test_a_desk_still_stalled_one_bound_after_the_interrupt_is_replaced():
    e = eng(nudged_at=NOW - 301)
    assert decide(e, row(last_movement_seconds=400)) == (
        tk.REPLACE, "still-stalled-after-interrupt (movement+cpu)")


def test_the_interrupt_gets_one_full_stall_bound_to_work():
    assert decide(eng(nudged_at=NOW - 200), row(last_movement_seconds=4000))[0] == tk.NONE


def test_a_desk_that_moved_after_the_interrupt_is_kept():
    assert decide(eng(nudged_at=NOW - 400), row(last_movement_seconds=30))[0] == tk.NONE


def test_a_gone_desk_is_replaced_at_once():
    assert decide(eng(), None) == (tk.REPLACE, "desk-gone")


@pytest.mark.parametrize("r", [None, row()])
def test_past_the_takeover_bound_nothing_is_done(r):
    decision, why = decide(eng(handovers=2), r)
    assert decision == tk.BOUND and "2 takeover" in why


def test_below_the_bound_takeover_still_happens():
    assert decide(eng(handovers=1), None)[0] == tk.REPLACE


# -- background CPU --------------------------------------------------------------------


def test_cpu_rate_excludes_the_agent_s_own_process():
    samples = iter([(1_000_000, 500_000), (1_258_000, 590_000)])
    clock = iter([100.0, 110.0])
    current = {}

    def cg(unit):
        current["s"] = next(samples)
        return current["s"][0]

    sampler = tk.CpuSampler(cgroup=cg, process=lambda pid: current["s"][1], clock=lambda: next(clock))
    assert sampler.rate("u", 42) == tk.PENDING    # first sample: ask again, never zero
    # measured on the hung desk: 258 ms cgroup, 90 ms the agent itself, over 10 s
    assert sampler.rate("u", 42) == pytest.approx(1.68)


def test_a_failed_read_or_a_new_pid_is_unmeasured():
    vals = iter([10, None, 20, 30])
    sampler = tk.CpuSampler(cgroup=lambda u: next(vals), process=lambda pid: 0, clock=iter([1.0, 2.0, 3.0, 4.0]).__next__)
    assert sampler.rate("u", 1) == tk.PENDING
    assert sampler.rate("u", 1) is None           # read failed: unmeasurable
    assert sampler.rate("u", 1) == tk.PENDING     # first sample after the failure
    assert sampler.rate("u", 2) == tk.PENDING     # a different process under the same unit


# -- the interrupt line ----------------------------------------------------------------


def test_the_line_names_the_request_by_pointer_and_asks_for_a_linked_reply():
    line = tk.interrupt_line(eng(), "stalled (movement+cpu)", now=NOW)
    assert "dm-a--b" in line and "2026-11-24T08:04:53.868+01:00" in line
    assert "--re 2026-11-24T08:04:53.868+01:00" in line and "\n" not in line


def test_the_interrupt_is_esc_then_line_then_enter():
    writes = []

    class Client:
        def write(self, label, data):
            writes.append((label, data))
            return 1

    tk.owner_interrupt("beta-desk", "hello  there", client=Client(), sleep=lambda s: None)
    assert writes == [("beta-desk", b"\x1b"), ("beta-desk", b"hello there"), ("beta-desk", b"\r")]


# -- the watch end to end, on real stores ---------------------------------------------


class Fakes:
    def __init__(self, tmp_path):
        self.now = NOW
        self.engagements = eng_mod.EngagementStore(str(tmp_path / "e.json"), clock=lambda: self.now)
        self.mandates = MandateStore(str(tmp_path / "m.json"))
        self.interrupts, self.stops, self.starts = [], [], []
        old = self.mandates.create(kind="desk", goal="Answer requests", project="beta", cwd="/x/beta",
                                   label="beta-desk", unit="set-agent-beta-desk.scope")
        self.old_mandate = old["id"]
        e = self.engagements.open(asker="alpha#aaaaaaaa", project="beta")
        self.engagements.set_desk(e["id"], label="beta-desk", seat="beta#0000dddd", mandate_id=old["id"])
        self.engagements.mark_sent(e["id"], room="dm-a--b", ts="2026-11-24T08:04:53.868+01:00")
        self.eid = e["id"]

    def watch(self, rows, cpu=None):
        def start_desk(project, *, requested_by, takeover):
            self.starts.append((project, requested_by, takeover))
            made = self.mandates.create(kind="desk", goal="Answer requests", project=project, cwd="/x",
                                        label="beta-desk", takeover=takeover)
            return Desk(project=project, label="beta-desk", seat="beta#0000eeee",
                        mandate_id=made["id"], started=True)

        return tk.TakeoverWatch(
            engagements=self.engagements, mandates=self.mandates, rows=rows,
            cpu=lambda unit, pid: cpu, interrupt=lambda label, line: self.interrupts.append((label, line)),
            stop=lambda label: self.stops.append(label), start_desk=start_desk, b=B,
            clock=lambda: self.now)


def _row_for(f, **over):
    return row(mandate={"id": f.old_mandate, "kind": "desk", "project": "beta", "ended": None}, **over)


def test_watch_interrupts_then_replaces_a_hung_desk(tmp_path):
    f = Fakes(tmp_path)
    f.now = NOW + 400
    out = f.watch([_row_for(f)]).run()
    assert out[0]["decision"] == tk.INTERRUPT
    assert f.interrupts and f.interrupts[0][0] == "beta-desk"
    assert f.engagements.get(f.eid)["nudged_at"] == NOW + 400
    assert f.stops == [] and f.starts == []

    f.now = NOW + 400 + 301
    out = f.watch([_row_for(f, last_movement_seconds=5000)]).run()
    assert out[0]["decision"] == tk.REPLACE
    assert f.stops == ["beta-desk"]
    assert f.mandates.get(f.old_mandate)["ended"]["reason"] == "replaced"
    project, requested_by, takeover = f.starts[0]
    assert project == "beta" and requested_by == "alpha#aaaaaaaa"
    assert takeover == {"room": "dm-a--b", "ts": "2026-11-24T08:04:53.868+01:00",
                        "asker": "alpha#aaaaaaaa", "from_seat": "beta#0000dddd",
                        "from_session": "sess-old", "engagement_id": f.eid}
    after = f.engagements.get(f.eid)
    assert after["state"] == "open" and after["handovers"] == 1 and after["nudged_at"] is None
    assert after["desk_seat"] == "beta#0000eeee"


def test_watch_replaces_a_gone_desk_without_stopping_anything(tmp_path):
    f = Fakes(tmp_path)
    out = f.watch([]).run()
    assert out[0]["decision"] == tk.REPLACE and f.stops == [] and len(f.starts) == 1
    assert f.starts[0][2]["from_session"] is None


def test_watch_leaves_a_busy_desk_alone(tmp_path):
    f = Fakes(tmp_path)
    f.now = NOW + 400
    out = f.watch([_row_for(f)], cpu=150.0).run()
    assert out[0]["decision"] == tk.NONE and not f.interrupts and not f.starts


def test_an_answered_engagement_is_not_watched(tmp_path):
    f = Fakes(tmp_path)
    f.engagements.mark_answered(f.eid, "2026-11-24T09:00:00.000+01:00")
    assert f.watch([]).run() == []


def test_a_failing_start_leaves_the_engagement_open_for_the_next_round(tmp_path):
    f = Fakes(tmp_path)
    w = f.watch([])

    def broken(*a, **k):
        raise RuntimeError("owner down")

    w.start_desk = broken
    out = w.run()
    assert out[0]["decision"] == "error"
    assert f.engagements.get(f.eid)["state"] == "open"
    assert f.engagements.get(f.eid)["handovers"] == 0


# -- the record and the context --------------------------------------------------------


def test_the_takeover_is_kept_on_the_mandate_and_shown_to_the_desk(tmp_path):
    store = MandateStore(str(tmp_path / "m.json"))
    made = store.create(kind="desk", goal="Answer requests that other agents address to beta",
                        project="beta", cwd="/x", label="beta-desk",
                        takeover={"room": "dm-a--b", "ts": "T1", "asker": "alpha#a",
                                  "from_seat": "beta#d", "from_session": "sess-old",
                                  "engagement_id": "e-1", "text": "must not be kept"})
    record = store.get(made["id"])
    assert "text" not in record["takeover"]
    context = mandate_delivery.render_context(record)
    for needle in ("TAKING OVER", "dm-a--b", "T1", "alpha#a", "beta#d", "sess-old",
                   "WITHOUT `--to` and WITHOUT `--re`", "`--re T1`", "openspec"):
        assert needle in context, needle


def test_a_desk_without_a_takeover_is_told_nothing_about_one(tmp_path):
    store = MandateStore(str(tmp_path / "m.json"))
    made = store.create(kind="desk", goal="Answer", project="beta", cwd="/x", label="beta-desk")
    assert "TAKING OVER" not in mandate_delivery.render_context(store.get(made["id"]))


def test_a_takeover_without_a_place_on_the_bus_is_dropped(tmp_path):
    store = MandateStore(str(tmp_path / "m.json"))
    made = store.create(kind="desk", goal="Answer", project="beta", cwd="/x", label="beta-desk",
                        takeover={"asker": "alpha#a"})
    assert store.get(made["id"])["takeover"] is None


def test_the_handover_fact_does_not_close_the_request(tmp_path):
    """An unlinked entry by the project is not the answer; only a linked one is."""
    root = tmp_path / "bus"
    room = root / "channels" / "dm-a--b"
    room.mkdir(parents=True)
    (room / "beta#0000eeee.md").write_text(
        "## 2026-11-24T09:00:00.000+01:00 — FACT  \nrequest moved\n", encoding="utf-8")
    assert eng_mod.linked_reply("dm-a--b", "2026-11-24T08:04:53.868+01:00", "beta", store_root=root) is None
    with open(room / "beta#0000eeee.md", "a", encoding="utf-8") as handle:
        handle.write("## 2026-11-24T09:10:00.000+01:00 — ANSWER (re: 2026-11-24T08:04:53.868+01:00)\nok\n")
    assert eng_mod.linked_reply("dm-a--b", "2026-11-24T08:04:53.868+01:00", "beta",
                                store_root=root) == "2026-11-24T09:10:00.000+01:00"
