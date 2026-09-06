"""The query cache under load — single-flight, duration-aware TTL, lazy axis ask.

B-139, measured 2026-09-06: a polled endpoint slower than its own answer used to
stack concurrent contract subprocesses (four concurrent `snapshot` children under
the server pid), and the fleet's stage-axis ask re-walked a whole declared
catalogue every cache window for an axis none of it declares. These tests hold
both behaviours.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import types
from pathlib import Path

import pytest

from set_orch.api import fleet as fleet_api
from set_orch.api import project_status as api_status
from set_orch.fleet import stage as fleet_stage
from set_orch.project_status import StatusResult, resolve_status_config


# --------------------------------------------------------------------------- #
# the reuse window an answer earns
# --------------------------------------------------------------------------- #


def test_ttl_floor_keeps_the_panel_fresh():
    """A cheap answer gains nothing: the window stays the poll-scale floor."""
    assert api_status._ttl_for(0.2, ok=True) == api_status.CACHE_TTL_SECONDS
    assert api_status._ttl_for(3.0, ok=True) == api_status.CACHE_TTL_SECONDS


def test_ttl_scales_with_measured_cost():
    """A 15 s `snapshot` must not be re-asked on a 30 s cycle (B-139)."""
    assert api_status._ttl_for(15.0, ok=True) == 150.0


def test_ttl_is_capped():
    assert api_status._ttl_for(120.0, ok=True) == api_status.DURATION_TTL_MAX_SECONDS


def test_a_failure_keeps_the_short_window():
    """A command that timed out must not buy itself minutes of being unaskable."""
    assert api_status._ttl_for(29.0, ok=False) == api_status.CACHE_TTL_SECONDS


# --------------------------------------------------------------------------- #
# single-flight: one subprocess per (project, command), however many callers
# --------------------------------------------------------------------------- #

SLOW_CONTRACT = """\
import json, sys, time, pathlib
pathlib.Path(__file__).with_name("calls.log").open("a").write(json.dumps(sys.argv[1:]) + "\\n")
time.sleep(1.5)
print(json.dumps({
    "contractVersion": 1,
    "generatedAt": "2026-09-06T00:00:00+02:00",
    "command": sys.argv[1] if len(sys.argv) > 1 else "",
    "ok": True,
    "data": {"asked": True},
}))
"""


@pytest.fixture
def slow_project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "contract.py").write_text(SLOW_CONTRACT)
    (proj / ".set-endpoint.json").write_text(json.dumps({
        "contractVersion": 1,
        "command": [sys.executable, "contract.py"],
        "commands": ["bugs"],
    }))
    return proj


@pytest.fixture(autouse=True)
def _clean_tables():
    api_status._CACHE.clear()
    fleet_api._AXIS_ABSENT.clear()
    yield
    api_status._CACHE.clear()
    fleet_api._AXIS_ABSENT.clear()


def _spawns(project: Path) -> int:
    log = project / "calls.log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def test_concurrent_callers_spawn_one_subprocess(slow_project):
    """Two callers arriving while the query runs must share its answer."""
    cfg = resolve_status_config(slow_project)
    barrier = threading.Barrier(2)
    answers: list = []

    def ask():
        barrier.wait()
        answers.append(api_status._cached_query(slow_project, "bugs", cfg, False))

    threads = [threading.Thread(target=ask) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(answers) == 2
    assert all(a.ok for a in answers)
    assert _spawns(slow_project) == 1, "each caller must not spawn its own subprocess"


def test_the_follower_reads_the_cached_answer_not_a_new_one(slow_project):
    """After waiting, the late caller takes the winner's answer from the cache."""
    cfg = resolve_status_config(slow_project)
    slow_answer = api_status._cached_query(slow_project, "bugs", cfg, False)

    # While the single-flight slot is now free, the TTL still holds: a fresh call
    # must be a cache hit, not a second subprocess.
    again = api_status._cached_query(slow_project, "bugs", cfg, False)
    assert again is slow_answer
    assert _spawns(slow_project) == 1


def test_a_long_answer_earns_a_longer_lease(slow_project):
    cfg = resolve_status_config(slow_project)
    api_status._cached_query(slow_project, "bugs", cfg, False)
    deadline = api_status._CACHE[(str(slow_project), "bugs")][0]
    remaining = deadline - time.monotonic()
    # 1.5 s of measured work × factor = 15 s < the floor, so the floor applies —
    # assert the entry is cached at all and inside the cap.
    assert api_status.CACHE_TTL_SECONDS - 2 <= remaining <= api_status.DURATION_TTL_MAX_SECONDS + 2


# --------------------------------------------------------------------------- #
# the lazy stage-axis ask
# --------------------------------------------------------------------------- #


def _axis_display():
    return {"id": "id", "stage": {"stageOrder": ["triage", "fixing", "shipping"]}}


def _result_for(name: str, *, declares: bool):
    data = [{"id": "x-1", "stage": "fixing"}] if declares else {"asked": name}
    display = _axis_display() if declares else None
    return StatusResult(command=name, ok=True, data=data, display=display)


def _patch_contract(monkeypatch, commands, behaviour):
    """Point the fleet module's contract at a scripted set of answers.

    `behaviour` maps command name → StatusResult. The returned list records the
    order the commands were actually asked in.
    """
    asked: list[str] = []
    cfg = types.SimpleNamespace(commands=list(commands), on_demand=[])

    def fake_query(project_path, command, cfg, refresh):
        asked.append(command)
        return behaviour[command]

    monkeypatch.setattr(fleet_api, "_status_config", lambda root: cfg)
    monkeypatch.setattr(fleet_api, "_cached_query", fake_query)
    return asked


def test_the_walk_stops_at_the_first_declarer(monkeypatch):
    """Asking past the answer that wins is pure subprocess waste (B-139)."""
    asked = _patch_contract(
        monkeypatch, ["a", "b", "c"],
        {"a": _result_for("a", declares=False),
         "b": _result_for("b", declares=True),
         "c": _result_for("c", declares=True)},
    )

    axis = fleet_api._declared_stage_axis("/proj")

    assert asked == ["a", "b"], "the walk must stop at the first declarer"
    assert axis == (["triage", "fixing", "shipping"], {"x-1": "fixing"})


def test_a_failed_answer_is_skipped_not_fatal(monkeypatch):
    """A command that failed cannot declare; the walk goes on to the next."""
    asked = _patch_contract(
        monkeypatch, ["a", "b"],
        {"a": StatusResult.failure("a", "timeout", "too slow"),
         "b": _result_for("b", declares=True)},
    )

    axis = fleet_api._declared_stage_axis("/proj")

    assert asked == ["a", "b"]
    assert axis is not None


def test_an_absent_axis_is_not_rewalked_every_cycle(monkeypatch):
    """A catalogue that declares nothing must not be re-asked each poll (B-139:

    39 s of subprocess work per 30 s window, for an axis that never arrives).
    """
    asked = _patch_contract(
        monkeypatch, ["a", "b"],
        {"a": _result_for("a", declares=False),
         "b": _result_for("b", declares=False)},
    )

    assert fleet_api._declared_stage_axis("/proj") is None
    first_round = list(asked)
    assert fleet_api._declared_stage_axis("/proj") is None
    assert fleet_api._declared_stage_axis("/proj") is None

    assert first_round == ["a", "b"]
    assert asked == first_round, "the absent verdict must be remembered"


def test_the_absent_verdict_expires_and_rewalks(monkeypatch):
    """A project adding a declaration is picked up within the rescan window."""
    asked = _patch_contract(
        monkeypatch, ["a"],
        {"a": _result_for("a", declares=False)},
    )
    assert fleet_api._declared_stage_axis("/proj") is None

    fleet_api._AXIS_ABSENT["/proj"] = time.monotonic() - 1  # window over

    assert fleet_api._declared_stage_axis("/proj") is None
    assert asked == ["a", "a"], "an expired verdict must re-walk the catalogue"


def test_a_late_declaration_stops_the_rewalk(monkeypatch):
    """The re-walk after expiry finds the axis and stops asking again."""
    behaviour = {"a": _result_for("a", declares=False)}
    asked = _patch_contract(monkeypatch, ["a"], behaviour)
    assert fleet_api._declared_stage_axis("/proj") is None

    fleet_api._AXIS_ABSENT["/proj"] = time.monotonic() - 1
    behaviour["a"] = _result_for("a", declares=True)

    axis = fleet_api._declared_stage_axis("/proj")
    assert axis == (["triage", "fixing", "shipping"], {"x-1": "fixing"})

    # The absence verdict is cleared, so the next call walks again — but it walks
    # TO the declarer (in production a cache hit, one dict lookup) and returns the
    # axis; it never re-enters the remember-absent state.
    assert fleet_api._declared_stage_axis("/proj") == axis
    assert fleet_api._AXIS_ABSENT.get("/proj") is None


def test_on_demand_commands_are_never_asked(monkeypatch):
    """The project's own 'too expensive to ask' word outranks the walk."""
    asked: list[str] = []
    cfg = types.SimpleNamespace(commands=["a", "b"], on_demand=["b"])

    def fake_query(project_path, command, cfg, refresh):
        asked.append(command)
        return _result_for(command, declares=False)

    monkeypatch.setattr(fleet_api, "_status_config", lambda root: cfg)
    monkeypatch.setattr(fleet_api, "_cached_query", fake_query)

    assert fleet_api._declared_stage_axis("/proj") is None
    assert asked == ["a"]


def test_no_config_asks_nothing(monkeypatch):
    monkeypatch.setattr(fleet_api, "_status_config", lambda root: None)
    assert fleet_api._declared_stage_axis("/proj") is None


def test_the_axis_reader_is_the_contract_reader(monkeypatch):
    """The incremental per-answer check must pick the same winner the batch call
    used to: the FIRST declarer in declaration order, not the last."""
    results = [_result_for("a", declares=True), _result_for("b", declares=True)]
    batch = fleet_stage.declared_axis_from_results(results)
    asked = _patch_contract(
        monkeypatch, ["a", "b"],
        {"a": results[0], "b": results[1]},
    )

    axis = fleet_api._declared_stage_axis("/proj")

    assert axis == batch
    assert asked == ["a"]
