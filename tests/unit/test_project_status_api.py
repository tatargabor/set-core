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
