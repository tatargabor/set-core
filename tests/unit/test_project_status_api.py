"""The status contract, seen from the HTTP boundary.

Two things are being protected here, and neither is "does the JSON look right".

**A command name travels from a URL into `subprocess.run`.** The project's declared
command list is the allowlist; the name shape is the floor under it. A request for
`--eval` or `../x` must never reach an argv, whether or not the project declared
anything.

**A gap must stay a gap.** A failed command renders as a reason, never as `0` or `[]`.
That is the whole difference between "the project has no open bugs" and "we could not
ask it", and a status panel that blurs the two is worse than no panel: it reports calm.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient  # noqa: E402

from set_orch.server import create_app  # noqa: E402
from set_orch.api import helpers as api_helpers  # noqa: E402
from set_orch.api import project_status as api_status  # noqa: E402


#: A stand-in contract: a python script that answers with a valid v1 envelope, and
#: records every argv it was handed so a test can prove what was NOT run.
FAKE_CONTRACT = """\
import json, sys, pathlib
argv = sys.argv[1:]
pathlib.Path(__file__).with_name("calls.log").open("a").write(json.dumps(argv) + "\\n")
cmd = argv[0] if argv else ""
if cmd == "boom":
    sys.stderr.write("internal detail that must not be echoed\\n")
    sys.exit(3)
payload = {"releases": {"total": 22}, "bugs": {"open": 7}}
print(json.dumps({
    "contractVersion": 1,
    "generatedAt": "2026-07-24T10:00:00+02:00",
    "command": cmd,
    "ok": True,
    "data": payload.get(cmd, {"asked": cmd}),
}))
"""


@pytest.fixture(autouse=True)
def clear_cache():
    """The answer cache is process-global; a leaked entry would fake a later test."""
    api_status._CACHE.clear()
    yield
    api_status._CACHE.clear()


@pytest.fixture
def project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "contract.py").write_text(FAKE_CONTRACT)
    (proj / ".set-endpoint.json").write_text(json.dumps({
        "contractVersion": 1,
        "command": [sys.executable, "contract.py"],
        "commands": ["releases", "bugs", "boom"],
    }))
    return proj


@pytest.fixture
def bare_project(tmp_path):
    """A project that publishes nothing — the common case."""
    proj = tmp_path / "bare"
    proj.mkdir()
    return proj


@pytest.fixture
def client(monkeypatch, tmp_path, project, bare_project):
    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps([
        {"name": "proj", "path": str(project)},
        {"name": "bare", "path": str(bare_project)},
    ]))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", pf)
    return TestClient(create_app(web_dist_dir=None))


def _calls(project):
    log = project / "calls.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


# ─── the contract route: answering without running anything ──────────────────

def test_contract_route_reports_what_will_be_called(client, project):
    data = client.get("/api/proj/project-status/contract").json()

    assert data["configured"] is True
    assert data["source"] == "manifest"
    assert data["commands"] == ["releases", "bugs", "boom"]
    assert _calls(project) == [], "asking WHAT will be called must not call it"


def test_a_project_without_a_contract_says_so_rather_than_erroring(client):
    resp = client.get("/api/bare/project-status/contract")

    assert resp.status_code == 200
    assert resp.json()["configured"] is False


def test_the_data_route_on_a_bare_project_is_empty_not_broken(client):
    """No contract is not an error — most projects publish none."""
    data = client.get("/api/bare/project-status").json()

    assert data["ok"] is False
    assert data["commands"] == {}
    assert data["contract"]["configured"] is False


def test_an_unknown_project_is_a_404(client):
    assert client.get("/api/nope/project-status").status_code == 404


# ─── what gets asked ─────────────────────────────────────────────────────────

def test_with_no_request_it_asks_exactly_what_the_project_declared(client, project):
    data = client.get("/api/proj/project-status").json()

    assert sorted(data["commands"]) == ["boom", "bugs", "releases"]
    assert [c[0] for c in _calls(project)] == ["releases", "bugs", "boom"]


def test_a_named_subset_asks_only_that(client, project):
    data = client.get("/api/proj/project-status?commands=bugs").json()

    assert list(data["commands"]) == ["bugs"]
    assert data["commands"]["bugs"]["data"] == {"open": 7}
    assert [c[0] for c in _calls(project)] == ["bugs"]


def test_a_command_the_project_never_declared_is_refused(client, project):
    resp = client.get("/api/proj/project-status?commands=secrets")

    assert resp.status_code == 404
    assert _calls(project) == [], "a refused command must not have been run"


@pytest.mark.parametrize("bad", ["--eval", "-rf", "../etc/passwd", "a b", "a;b", "A"])
def test_a_name_that_is_not_a_command_name_never_reaches_argv(client, project, bad):
    """The shape check is the floor: it holds even where an allowlist would not."""
    resp = client.get("/api/proj/project-status", params={"commands": bad})

    assert resp.status_code in (400, 404)
    assert _calls(project) == []


def test_a_contract_declaring_nothing_asks_nothing_and_explains(client, tmp_path,
                                                                monkeypatch):
    """Undeclared is not a licence for set-core to guess at command names."""
    proj = tmp_path / "undeclared"
    proj.mkdir()
    (proj / "contract.py").write_text(FAKE_CONTRACT)
    (proj / ".set-endpoint.json").write_text(json.dumps({
        "contractVersion": 1,
        "command": [sys.executable, "contract.py"],
    }))
    pf = tmp_path / "p2.json"
    pf.write_text(json.dumps([{"name": "undeclared", "path": str(proj)}]))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", pf)
    client = TestClient(create_app(web_dist_dir=None))

    data = client.get("/api/undeclared/project-status").json()

    assert data["commands"] == {}
    assert "*" in data["gaps"]
    assert _calls(proj) == []


# ─── gaps stay gaps ──────────────────────────────────────────────────────────

def test_one_failing_command_does_not_blank_the_others(client):
    data = client.get("/api/proj/project-status").json()

    assert data["commands"]["releases"]["ok"] is True
    assert data["commands"]["releases"]["data"] == {"total": 22}
    assert data["commands"]["boom"]["ok"] is False
    assert data["ok"] is False


def test_a_failure_is_reported_as_a_gap_never_as_a_number(client):
    data = client.get("/api/proj/project-status?commands=boom").json()

    entry = data["commands"]["boom"]
    assert entry["data"] is None, "a failed command must not carry a value at all"
    assert entry["errorClass"] == "nonzero-exit"
    assert "boom" in data["gaps"]


def test_the_projects_stderr_is_not_echoed_back_over_http(client):
    """Failure text is set-core's; the project's own words may quote its domain."""
    body = client.get("/api/proj/project-status?commands=boom").text

    assert "internal detail" not in body


# ─── the cache: a poll must not become load ──────────────────────────────────

def test_repeat_requests_reuse_the_answer(client, project):
    client.get("/api/proj/project-status?commands=bugs")
    client.get("/api/proj/project-status?commands=bugs")

    assert [c[0] for c in _calls(project)] == ["bugs"]


def test_refresh_bypasses_it(client, project):
    client.get("/api/proj/project-status?commands=bugs")
    client.get("/api/proj/project-status?commands=bugs&refresh=true")

    assert [c[0] for c in _calls(project)] == ["bugs", "bugs"]


def test_a_failure_is_cached_too(client, project):
    """A broken contract otherwise turns one defect into a subprocess per poll."""
    client.get("/api/proj/project-status?commands=boom")
    client.get("/api/proj/project-status?commands=boom")

    assert [c[0] for c in _calls(project)] == ["boom"]


def test_the_cache_is_per_project_not_per_command_name(client, project, bare_project):
    """Two projects asked the same question must not share an answer."""
    client.get("/api/proj/project-status?commands=bugs")
    data = client.get("/api/bare/project-status?commands=bugs").json()

    assert data["contract"]["configured"] is False
    assert data["commands"] == {}


def test_nothing_from_the_answer_is_written_into_the_project(client, project):
    """The read side persists nothing — the contract's own log is the only new file."""
    before = {p.name for p in project.iterdir()}
    client.get("/api/proj/project-status")
    after = {p.name for p in project.iterdir()}

    assert after - before <= {"calls.log"}


# ─── writes: a separate list, a separate function, a separate route ──────────

WRITE_CONTRACT = """\
import json, sys, pathlib
argv = sys.argv[1:]
pathlib.Path(__file__).with_name("calls.log").open("a").write(json.dumps(argv) + "\\n")
cmd = argv[0] if argv else ""
print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True,
                  "data": {"recorded": True, "argv": argv[1:]}}))
"""


@pytest.fixture
def writable(tmp_path, monkeypatch):
    """A project declaring one read command and one write command."""
    proj = tmp_path / "w"
    proj.mkdir()
    (proj / "contract.py").write_text(WRITE_CONTRACT)
    (proj / ".set-endpoint.json").write_text(json.dumps({
        "contractVersion": 1,
        "command": [sys.executable, "contract.py"],
        "commands": ["releases"],
        "writeCommands": ["ack"],
    }))
    pf = tmp_path / "wp.json"
    pf.write_text(json.dumps([{"name": "w", "path": str(proj)}]))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", pf)
    return proj, TestClient(create_app(web_dist_dir=None))


def test_a_declared_write_is_performed(writable):
    proj, client = writable
    resp = client.post("/api/w/project-status/write/ack",
                       json={"release": "1.2.3", "index": 4, "env": "test"})

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert _calls(proj) == [["ack", "--release", "1.2.3", "--index", "4", "--env", "test"]]


def test_a_read_command_cannot_be_invoked_as_a_write(writable):
    """The separation is the safety property; precedence would dissolve it."""
    proj, client = writable
    resp = client.post("/api/w/project-status/write/releases", json={})

    assert resp.status_code == 404
    assert _calls(proj) == []


def test_a_write_command_is_never_reachable_through_the_read_route(writable):
    """A page load walks the read list — it must not be able to arrive at a write."""
    proj, client = writable
    resp = client.get("/api/w/project-status?commands=ack")

    assert resp.status_code == 404
    assert _calls(proj) == []


def test_the_default_page_load_asks_only_read_commands(writable):
    proj, client = writable
    client.get("/api/w/project-status")

    assert [c[0] for c in _calls(proj)] == ["releases"]


def test_a_project_declaring_no_writes_can_never_be_written_to(client, project):
    resp = client.post("/api/proj/project-status/write/ack", json={})

    assert resp.status_code == 404
    assert _calls(project) == []


@pytest.mark.parametrize("flag", ["--evil", "a b", "A", "", "a;b"])
def test_a_malformed_argument_name_never_reaches_argv(writable, flag):
    proj, client = writable
    resp = client.post("/api/w/project-status/write/ack", json={flag: "x"})

    assert resp.json()["ok"] is False
    assert resp.json()["errorClass"] == "invalid-argument"
    assert _calls(proj) == []


def test_a_value_that_looks_like_a_flag_is_refused_not_escaped(writable):
    """argv is positional: a dashed value shifts everything after it, silently."""
    proj, client = writable
    resp = client.post("/api/w/project-status/write/ack", json={"by": "-rf"})

    assert resp.json()["errorClass"] == "invalid-argument"
    assert _calls(proj) == []


def test_a_successful_write_drops_the_read_cache(writable):
    """Showing a step as un-acknowledged right after acknowledging it is its own lie."""
    proj, client = writable
    client.get("/api/w/project-status")
    client.post("/api/w/project-status/write/ack", json={"env": "test"})
    client.get("/api/w/project-status")

    assert [c[0] for c in _calls(proj)] == ["releases", "ack", "releases"]


def test_a_failed_write_leaves_the_cache_alone(writable):
    """Nothing changed on the project's side, so nothing needs re-reading."""
    proj, client = writable
    client.get("/api/w/project-status")
    client.post("/api/w/project-status/write/ack", json={"by": "-x"})
    client.get("/api/w/project-status")

    assert [c[0] for c in _calls(proj)] == ["releases"]


def test_the_contract_route_reports_the_write_list_separately(writable):
    _, client = writable
    data = client.get("/api/w/project-status/contract").json()

    assert data["commands"] == ["releases"]
    assert data["writeCommands"] == ["ack"]


def test_a_name_in_both_lists_is_refused_from_both(tmp_path, monkeypatch):
    """A command cannot be safe to call on a page load and also change something."""
    proj = tmp_path / "both"
    proj.mkdir()
    (proj / "contract.py").write_text(WRITE_CONTRACT)
    (proj / ".set-endpoint.json").write_text(json.dumps({
        "contractVersion": 1,
        "command": [sys.executable, "contract.py"],
        "commands": ["ack", "releases"],
        "writeCommands": ["ack"],
    }))
    pf = tmp_path / "bp.json"
    pf.write_text(json.dumps([{"name": "both", "path": str(proj)}]))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", pf)
    client = TestClient(create_app(web_dist_dir=None))

    contract = client.get("/api/both/project-status/contract").json()
    assert contract["commands"] == ["releases"]
    assert contract["writeCommands"] == []

    assert client.post("/api/both/project-status/write/ack", json={}).status_code == 404
    assert client.get("/api/both/project-status?commands=ack").status_code == 404
    assert _calls(proj) == []


# ─── which answer the surface opens on ───────────────────────────────────────

def test_the_contract_route_reports_a_declared_primary(client, project):
    """The surface needs it before it renders, so it travels with the contract."""
    manifest = json.loads((project / ".set-endpoint.json").read_text())
    manifest["primary"] = "bugs"
    (project / ".set-endpoint.json").write_text(json.dumps(manifest))

    data = client.get("/api/proj/project-status/contract").json()

    assert data["primary"] == "bugs"
    assert _calls(project) == [], "a preference must not cost a spawn"


def test_a_refused_primary_reaches_the_surface_as_null_not_as_itself(client, project):
    """Otherwise the page reports a preference the loader already threw away, and the
    reader is told the project chose something it did not get."""
    manifest = json.loads((project / ".set-endpoint.json").read_text())
    manifest["primary"] = "not-declared-anywhere"
    (project / ".set-endpoint.json").write_text(json.dumps(manifest))

    assert client.get("/api/proj/project-status/contract").json()["primary"] is None


def test_a_project_without_a_contract_reports_no_primary_either(client):
    assert client.get("/api/bare/project-status/contract").json()["primary"] is None


# ─── expensive answers are not asked for by a page load ──────────────────────

def _mark_on_demand(project, name):
    manifest = json.loads((project / ".set-endpoint.json").read_text())
    manifest["onDemand"] = [name]
    (project / ".set-endpoint.json").write_text(json.dumps(manifest))


def test_a_page_load_does_not_run_an_on_demand_command(client, project):
    _mark_on_demand(project, "bugs")

    data = client.get("/api/proj/project-status").json()

    assert "releases" in data["commands"]
    assert "bugs" not in data["commands"], "an expensive answer must not run by itself"
    assert [c[0] for c in _calls(project)] == ["releases", "boom"]


def test_asking_for_it_by_name_still_works(client, project):
    """The flag narrows what happens automatically, never what a person may request."""
    _mark_on_demand(project, "bugs")

    data = client.get("/api/proj/project-status?commands=bugs").json()

    assert data["commands"]["bugs"]["ok"] is True
    assert [c[0] for c in _calls(project)] == ["bugs"]


def test_the_contract_route_reports_the_on_demand_list(client, project):
    _mark_on_demand(project, "bugs")

    assert client.get("/api/proj/project-status/contract").json()["onDemand"] == ["bugs"]
