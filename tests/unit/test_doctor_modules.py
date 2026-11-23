"""doctor-module-contract: set-doctor as the umbrella over declared module doctors.

Each test drives one spec scenario on a sandbox machine: a temp HOME and SET_CONFIG_DIR with a
`doctors.d`, a temp registry, and module doctors that are tiny scripts printing a fixed report."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from set_doctor import modules as m
from set_doctor.checks import Check, Context, bus_status, check_project, run_modules, stale_check, stale_entries
from set_doctor.cli import exit_code, payload, render_text

REPO = Path(__file__).resolve().parents[2]


def git_init(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    return p


@pytest.fixture
def box(tmp_path):
    cfg = tmp_path / "cfg"
    (cfg / "doctors.d").mkdir(parents=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    env = {"HOME": str(tmp_path / "home"), "PATH": f"{bindir}:{os.environ['PATH']}", "SET_CONFIG_DIR": str(cfg)}
    ctx = Context(root=str(REPO), home=env["HOME"], offline=True, env=env)
    return ctx, tmp_path, cfg / "doctors.d", bindir


def module_script(bindir: Path, name: str, report, *, sleep: float = 0, log: Path = None) -> str:
    """A fake module doctor: prints `report` (dict → JSON, str → as is); appends its env marker
    to `log` when given, so a test can count runs and see SET_DOCTOR_CHILD."""
    body = [f"#!{sys.executable}", "import json, os, sys, time"]
    if log:
        body.append(f"open({str(log)!r}, 'a').write(os.environ.get('SET_DOCTOR_CHILD', '-') + '\\n')")
    if sleep:
        body.append(f"time.sleep({sleep})")
    text = report if isinstance(report, str) else json.dumps(report)
    body.append(f"sys.stdout.write({text!r})")
    p = bindir / name
    p.write_text("\n".join(body) + "\n")
    p.chmod(0o755)
    return name


def declare(ddir: Path, module: str, command, contract=m.CONTRACT, **extra):
    (ddir / f"{module}.json").write_text(json.dumps(
        {"module": module, "command": command, "contract": contract, "install": f"install-{module}", **extra}))


def doctor1(*checks, module="example"):
    return {"schema": "doctor/1", "module": module, "checks": list(checks)}


def by(checks, **kw):
    return [c for c in checks if all(getattr(c, k) == v for k, v in kw.items())]


# ── contract ────────────────────────────────────────────────────────────────


def test_a_conforming_module_report_is_merged(box):
    ctx, tmp, ddir, bindir = box
    cmd = module_script(bindir, "ex-doctor", doctor1(
        {"section": "x", "name": "thing", "status": "warn", "detail": "drifted", "fix": "ex-fix"}))
    declare(ddir, "example", [cmd])
    decls, problems = m.load_declarations(ctx.env)
    assert not problems
    recs = run_modules(ctx, decls, {})
    [c] = by(recs, name="thing")
    assert c.status == "warn" and c.fix == "ex-fix" and c.module == "example"
    assert c.to_dict()["module"] == "example"


def test_an_unknown_contract_is_a_failure_not_an_absence(box):
    ctx, tmp, ddir, bindir = box
    cmd = module_script(bindir, "ex-doctor", {"schema": "doctor/9", "checks": []})
    declare(ddir, "example", [cmd])
    decls, _ = m.load_declarations(ctx.env)
    recs = run_modules(ctx, decls, {})
    assert [c.status for c in recs] == ["fail"]
    assert "doctor/9" in recs[0].detail and recs[0].module == "example"
    assert not by(recs, status="ok"), "never shown as clean"


def test_a_status_outside_the_four_is_rejected(box):
    ctx, tmp, ddir, bindir = box
    cmd = module_script(bindir, "ex-doctor", doctor1({"name": "a", "status": "blocked", "detail": ""}))
    declare(ddir, "example", [cmd])
    decls, _ = m.load_declarations(ctx.env)
    [c] = run_modules(ctx, decls, {})
    assert c.status == "fail" and "status outside" in c.detail


# ── discovery ───────────────────────────────────────────────────────────────


def test_a_new_module_is_picked_up_without_a_code_change(box):
    ctx, tmp, ddir, bindir = box
    assert run_modules(ctx, m.load_declarations(ctx.env)[0], {}) == []
    cmd = module_script(bindir, "ex-doctor", doctor1({"name": "alive", "status": "ok", "detail": "fine"}))
    declare(ddir, "example", [cmd])
    recs = run_modules(ctx, m.load_declarations(ctx.env)[0], {})
    assert by(recs, name="alive", module="example")


def test_a_broken_declaration_is_reported_and_the_rest_still_run(box):
    ctx, tmp, ddir, bindir = box
    (ddir / "broken.json").write_text("{not json")
    cmd = module_script(bindir, "ex-doctor", doctor1({"name": "alive", "status": "ok", "detail": ""}))
    declare(ddir, "example", [cmd])
    decls, problems = m.load_declarations(ctx.env)
    assert [p.status for p in problems] == ["fail"] and str(ddir / "broken.json") in problems[0].detail
    assert by(run_modules(ctx, decls, {}), name="alive")


def test_a_module_declared_twice_fails_naming_both_files(box):
    ctx, tmp, ddir, bindir = box
    declare(ddir, "example", ["a"])
    (ddir / "example-again.json").write_text(json.dumps(
        {"module": "example", "command": ["b"], "contract": m.CONTRACT, "install": "x"}))
    decls, problems = m.load_declarations(ctx.env)
    assert "example" not in decls
    [p] = problems
    assert p.status == "fail" and "example.json" in p.detail and "example-again.json" in p.detail


def test_declarations_follow_the_config_dir_resolution(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    assert m.doctors_dir(env) == str(tmp_path / "xdg" / "set-core" / "doctors.d")
    assert m.doctors_dir({**env, "SET_CONFIG_DIR": str(tmp_path / "c")}) == str(tmp_path / "c" / "doctors.d")


# ── running and attribution ─────────────────────────────────────────────────


def test_a_per_project_record_lands_on_its_project(box):
    ctx, tmp, ddir, bindir = box
    proj = git_init(tmp / "proj")
    cmd = module_script(bindir, "ex-doctor", doctor1(
        {"section": "x", "name": "rule", "status": "fail", "detail": "broken", "fix": "f", "path": str(proj)},
        {"section": "x", "name": "elsewhere", "status": "warn", "detail": "d", "fix": "f", "path": str(tmp / "nope")}))
    declare(ddir, "example", [cmd])
    recs = run_modules(ctx, m.load_declarations(ctx.env)[0], {"proj": {"path": str(proj)}})
    [c] = by(recs, name="rule")
    assert c.project == "proj" and c.section == "project" and c.module == "example"
    d = c.to_dict()
    assert d["project"] == "proj" and d["module"] == "example" and "path" not in d
    [u] = by(recs, name="elsewhere")
    assert u.project is None and u.section == "modules" and str(tmp / "nope") in u.detail
    text = render_text(ctx, recs, show_all=False)
    assert "example:rule" in text.split("PROJECTS", 1)[1].split("MODULES", 1)[0]
    assert "example:elsewhere" in text.split("MODULES", 1)[1]


def test_a_module_that_hangs_is_a_timeout_fail(box):
    ctx, tmp, ddir, bindir = box
    cmd = module_script(bindir, "slow-doctor", doctor1(), sleep=10)
    declare(ddir, "slow", [cmd], timeout_s=1)
    fast = module_script(bindir, "ex-doctor", doctor1({"name": "alive", "status": "ok", "detail": ""}))
    declare(ddir, "example", [fast])
    recs = run_modules(ctx, m.load_declarations(ctx.env)[0], {})
    [s] = by(recs, module="slow")
    assert s.status == "fail" and "timed out" in s.detail
    assert by(recs, name="alive"), "the rest of the report is complete"


def test_each_module_runs_once_with_the_child_marker(box):
    ctx, tmp, ddir, bindir = box
    log = tmp / "runs.log"
    cmd = module_script(bindir, "ex-doctor", doctor1(), log=log)
    declare(ddir, "example", [cmd])
    run_modules(ctx, m.load_declarations(ctx.env)[0], {"a": {"path": "/x"}, "b": {"path": "/y"}})
    assert log.read_text().splitlines() == ["1"], "once, and with SET_DOCTOR_CHILD=1"


# ── not installed ───────────────────────────────────────────────────────────


def test_a_second_developers_machine_without_the_module(box):
    ctx, tmp, ddir, bindir = box
    declare(ddir, "example", ["no-such-doctor-anywhere", "--json"])
    [c] = run_modules(ctx, m.load_declarations(ctx.env)[0], {})
    assert c.status == "warn" and "not installed on this machine" in c.detail and c.fix == "install-example"


# ── adapters ────────────────────────────────────────────────────────────────


SAC_REPORT = lambda path, **p: {"schema": "sac.doctor/1", "projects": [  # noqa: E731
    {"project": "proj", "path": path, "hooks": p.get("hooks", {}), "live": p.get("live", []),
     "verdict": p.get("verdict", "off"), "problems": p.get("problems", [])}]}


def test_no_declaration_no_regression(box):
    """Empty doctors.d: every project still gets its bus and kb records, from the built-ins."""
    ctx, tmp, ddir, bindir = box
    proj = git_init(tmp / "proj")
    out = check_project(ctx, "proj", {"path": str(proj)}, {}, {})
    assert {c.name for c in out} == {"path", "deploy", "mcp", "bus", "kb"}
    assert by(out, name="bus")[0].module == "sac" and by(out, name="kb")[0].module == "set-kb"


def test_a_declaration_replaces_the_built_in_run(box, monkeypatch):
    ctx, tmp, ddir, bindir = box
    from set_doctor import checks as ck

    log = tmp / "sac.log"
    proj = git_init(tmp / "proj")
    cmd = module_script(bindir, "my-sac", SAC_REPORT(str(proj), verdict="ok"), log=log)
    declare(ddir, "sac", [cmd], contract=m.SAC_CONTRACT)
    (tmp / "cfg" / "projects.json").write_text(json.dumps({"projects": {"proj": {"path": str(proj)}}}))
    # the built-in launcher would be a second run: make it loud if it happens
    module_script(bindir, "sac", "BUILT-IN RAN", log=tmp / "builtin.log")
    quiet_machine(monkeypatch, ck)
    checks = ck.run_all(ctx)
    assert log.read_text().splitlines() == ["1"]
    assert not (tmp / "builtin.log").exists()
    [sac] = by(checks, section="bus", name="sac")
    assert sac.status == "ok" and sac.module == "sac"


def test_the_family_doctors_repository_findings_reach_their_projects(box):
    ctx, tmp, ddir, bindir = box
    report = {"schema": "aiplus-doctor/1", "machine": [
        {"check": "set-doctor", "status": "fail", "detail": "exit 1", "fix": "set-doctor"},
        {"check": "platform tag", "status": "warn", "detail": "behind", "fix": "git pull"}],
        "repos": {"known": [{"check": "5 guards", "status": "fail", "detail": "no guard", "fix": "add it"}],
                  "unknown": [{"check": "2 devkit", "status": "warn", "detail": "old", "fix": "update"}]}}
    cmd = module_script(bindir, "fam-doctor", report)
    declare(ddir, "aiplus", [cmd, "--json"], contract=m.AIPLUS_CONTRACT)
    recs = run_modules(ctx, m.load_declarations(ctx.env)[0], {"known": {"path": "/k"}})
    [g] = by(recs, name="5 guards")
    assert g.project == "known" and g.section == "project" and g.status == "fail" and g.module == "aiplus"
    [u] = by(recs, name="2 devkit")
    assert u.project is None and u.section == "modules" and "unknown" in u.detail
    assert by(recs, name="platform tag", section="modules")
    assert not by(recs, name="set-doctor"), "its verdict on the run reading it is self-referential"


def quiet_machine(monkeypatch, ck):
    """Only the module and project paths matter here; the machine sections are other tests'."""
    for f in ("check_install", "check_checkout", "check_tools", "check_mcp_probe", "check_provider", "check_github"):
        monkeypatch.setattr(ck, f, lambda ctx: [])
    monkeypatch.setattr(ck, "check_relay", lambda ctx: Check("bus", "relay", "skip", "test"))


# ── recursion ───────────────────────────────────────────────────────────────


def test_the_family_doctor_is_declared_and_calls_set_doctor(box, monkeypatch):
    """A declared module that runs set-doctor: the inner run runs no module doctors."""
    ctx, tmp, ddir, bindir = box
    from set_doctor import checks as ck

    log = tmp / "inner.log"
    inner = bindir / "fam-doctor"
    inner.write_text(f"""#!{sys.executable}
import json, os, subprocess, sys
r = subprocess.run([sys.executable, {str(REPO / 'bin' / 'set-doctor')!r}, "--offline", "--json",
                    "--project", "none"], capture_output=True, text=True, timeout=300)
d = json.loads(r.stdout)
open({str(log)!r}, "a").write(json.dumps([c for c in d["checks"] if c["section"] == "modules"]) + "\\n")
print(json.dumps({{"schema": "doctor/1", "module": "fam", "checks": [
    {{"name": "inner", "status": "ok", "detail": "ran"}}]}}))
""")
    inner.chmod(0o755)
    declare(ddir, "fam", ["fam-doctor"])
    quiet_machine(monkeypatch, ck)
    monkeypatch.setattr(ck, "sac_doctor", lambda ctx, decl=None: (None, Check("bus", "sac", "skip", "test")))
    checks = ck.run_all(ctx)
    assert by(checks, name="inner", module="fam"), "the outer run finished and merged the module"
    [line] = log.read_text().splitlines()
    inner_modules = json.loads(line)
    assert [c["status"] for c in inner_modules] == ["skip"] and "SET_DOCTOR_CHILD" in inner_modules[0]["detail"]


# ── set-doctor/1 output ─────────────────────────────────────────────────────


def test_a_modules_record_says_where_it_came_from(tmp_path):
    proj = git_init(tmp_path / "proj")
    [c] = bus_status({os.path.realpath(proj): {"hooks": {}, "live": [], "verdict": "off"}}, str(proj))
    d = payload(Context(root=str(REPO), home=str(tmp_path)), [c], exit_code([c], False))
    assert d["schema"] == "set-doctor/1" and d["checks"][0]["module"] == "sac"


# ── stale registry ──────────────────────────────────────────────────────────


def test_a_registered_path_is_gone(tmp_path):
    keep = git_init(tmp_path / "keep")
    stripped = tmp_path / "stripped"
    (stripped / ".set").mkdir(parents=True)
    reg = {"keep": {"path": str(keep)}, "gone": {"path": str(tmp_path / "gone")},
           "stripped": {"path": str(stripped)}}
    alive, stale = stale_entries(reg, sorted(reg))
    assert alive == ["keep"] and stale == {"gone": "gone", "stripped": "not a git repository"}
    c = stale_check(stale)
    assert c.status == "warn" and c.name == "stale"
    assert "gone: gone" in c.detail and "not a git repository: stripped" in c.detail
    assert "gone" in c.fix and "stripped" in c.fix and "set-project remove" in c.fix
    assert exit_code([c], strict=False) == 0, "bookkeeping does not set the exit code"


# ── bus severity (design D4) ────────────────────────────────────────────────


def sac_entry(**kw):
    return {"hooks": kw.get("hooks", {}), "live": kw.get("live", []), "verdict": kw.get("verdict", "off"),
            "problems": kw.get("problems", []), "rooms": []}


ALL = {k: ["settings.json:portable"] for k in ("session-start", "stop", "heartbeat", "watch-guard")}


def test_a_live_session_in_a_project_off_the_bus(tmp_path):
    proj = git_init(tmp_path / "proj")
    [c] = bus_status({os.path.realpath(proj): sac_entry(live=["proj#abc"])}, str(proj))
    assert c.status == "fail" and "proj#abc" in c.detail
    assert "session-start" in c.detail and "watch-guard" in c.detail
    assert c.fix == f"cd {proj} && sac install"


def test_a_live_session_without_the_watch_guard(tmp_path):
    proj = git_init(tmp_path / "proj")
    hooks = {**ALL, "watch-guard": []}
    [c] = bus_status({os.path.realpath(proj): sac_entry(hooks=hooks, live=["proj#abc"], verdict="warn")}, str(proj))
    assert c.status == "fail" and "watch-guard" in c.detail and "session-start hook" not in c.detail


def test_off_the_bus_and_idle(tmp_path):
    proj = git_init(tmp_path / "proj")
    [c] = bus_status({os.path.realpath(proj): sac_entry()}, str(proj))
    assert c.status == "warn" and "not on the agent bus" in c.detail


def test_a_hook_wired_twice(tmp_path):
    proj = git_init(tmp_path / "proj")
    hooks = {**ALL, "session-start": ["settings.json:portable", "plugin x@1:portable:plugin"]}
    out = bus_status({os.path.realpath(proj): sac_entry(hooks=hooks, live=["proj#a"], verdict="ok")}, str(proj))
    [ok] = by(out, name="bus")
    [dup] = by(out, name="bus wiring")
    assert ok.status == "ok"
    assert dup.status == "warn" and "session-start runs from 2 carriers" in dup.detail
    assert "settings.json:portable" in dup.detail and "plugin x@1:portable:plugin" in dup.detail
