"""set-doctor (change set-doctor): the developer-machine check.

Most tests drive one check function against a sandbox machine — an empty HOME,
a temp registry, a temp Claude config, a link directory — so each spec scenario
is measured on its own. Two run the real command end to end in that sandbox,
the shape of a second developer's fresh machine."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from set_doctor.checks import (
    Check, Context, archived_check, archived_entries, check_checkout, check_install, check_project, check_tools, deployed_version,
    installer_commands, mcp_registration,
)
from set_doctor.cli import exit_code
from set_doctor.mcp_probe import probe

REPO = Path(__file__).resolve().parents[2]
GIT_ID = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *GIT_ID, *args], check=True, capture_output=True, text=True).stdout


def commit(path, msg="c"):
    (Path(path) / f"{msg}.txt").write_text(msg)
    git(path, "add", ".")
    git(path, "commit", "-qm", msg)
    return git(path, "rev-parse", "HEAD").strip()


@pytest.fixture
def machine(tmp_path):
    """A sandbox machine: HOME, link dir with every installer command, registry, Claude config."""
    home = tmp_path / "home"
    links = home / ".local" / "bin"
    links.mkdir(parents=True)
    for name in installer_commands(str(REPO)):
        (links / name).symlink_to(REPO / "bin" / name)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "projects.json").write_text(json.dumps({"projects": {}}))
    claude = tmp_path / "claude"
    claude.mkdir()
    (claude / ".claude.json").write_text(json.dumps({"projects": {}}))
    env = {"HOME": str(home), "PATH": f"{links}:{os.environ['PATH']}", "SET_CONFIG_DIR": str(cfg),
           "CLAUDE_CONFIG_DIR": str(claude)}
    ctx = Context(root=str(REPO), home=str(home), offline=True, env=env)
    return ctx, tmp_path


def by(checks, name):
    [c] = [c for c in checks if c.name == name]
    return c


# ── status and exit code ─────────────────────────────────────────────────────


def test_a_failing_check_sets_the_exit_code():
    checks = [Check("x", "a", "ok", ""), Check("x", "b", "fail", "broken", "do-this")]
    assert exit_code(checks, strict=False) == 1
    assert checks[1].to_dict()["fix"] == "do-this"


def test_warnings_alone_pass_unless_strict():
    checks = [Check("x", "a", "ok", ""), Check("x", "b", "warn", "behind", "pull"), Check("x", "c", "skip", "n/a")]
    assert exit_code(checks, strict=False) == 0
    assert exit_code(checks, strict=True) == 1


# ── install ──────────────────────────────────────────────────────────────────


def test_the_install_is_measured_against_the_installers_list(machine):
    ctx, _ = machine
    names = installer_commands(str(REPO))
    assert "set-doctor" in names and "set-kb" in names, "read from install.sh itself"
    assert by(check_install(ctx), "commands").status == "ok"


def test_a_missing_installer_command_fails_and_names_it(machine):
    ctx, _ = machine
    os.unlink(os.path.join(ctx.link_dir, "set-kb"))
    c = by(check_install(ctx), "commands")
    assert c.status == "fail" and "set-kb" in c.detail
    assert c.fix == f"cd {REPO} && ./install.sh"


def test_a_command_linked_into_another_checkout_warns(machine):
    ctx, tmp = machine
    other = tmp / "other-checkout" / "bin"
    other.mkdir(parents=True)
    (other / "set-kb").write_text("#!/bin/sh\n")
    os.unlink(os.path.join(ctx.link_dir, "set-kb"))
    os.symlink(other / "set-kb", os.path.join(ctx.link_dir, "set-kb"))
    c = by(check_install(ctx), "commands")
    assert c.status == "warn" and "set-kb" in c.detail and str(other) in c.detail


def test_the_link_dir_must_be_on_path(machine):
    ctx, _ = machine
    ctx.env["PATH"] = "/usr/bin:/bin"
    c = by(check_install(ctx), "PATH")
    assert c.status == "fail" and ctx.link_dir in c.fix


# ── checkout ─────────────────────────────────────────────────────────────────


def test_a_checkout_behind_its_upstream_warns_with_the_count(tmp_path):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
    git(work, "checkout", "-qb", "main")
    commit(work, "one")
    git(work, "push", "-q", "-u", "origin", "main")
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True, capture_output=True)
    commit(other, "two")
    commit(other, "three")
    git(other, "push", "-q")
    ctx = Context(root=str(work), home=str(tmp_path), offline=False)
    c = by(check_checkout(ctx), "upstream")
    assert c.status == "warn" and "2 commit(s) behind origin/main" in c.detail
    assert c.fix == f"git -C {work} pull"
    # --offline compares with the refs on disk, and says so
    off = by(check_checkout(Context(root=str(work), home=str(tmp_path), offline=True)), "upstream")
    assert "not fetched" in off.detail


# ── projects ─────────────────────────────────────────────────────────────────


def project_repo(tmp_path, name="proj") -> Path:
    p = tmp_path / name
    p.mkdir()
    (p / ".gitignore").write_text(".set/\n")
    git(p, "init", "-q")
    return p


def test_a_registered_path_that_is_gone_is_not_a_fail(machine):
    """doctor-module-contract D5: a gone path is bookkeeping. run_all folds it into one `stale`
    record (tests/unit/test_doctor_modules.py); a direct caller still gets a record, as a warn."""
    ctx, tmp = machine
    [c] = check_project(ctx, "gone", {"path": str(tmp / "nowhere")}, {}, {})
    assert c.status == "warn" and "does not exist" in c.detail and str(tmp / "nowhere") in c.detail
    assert c.project == "gone"


def test_a_project_behind_this_checkout(tmp_path):
    root = tmp_path / "setcore"
    root.mkdir()
    git(root, "init", "-q")
    old = commit(root, "a")
    for m in ("b", "c", "d"):
        commit(root, m)
    proj = project_repo(tmp_path)
    (proj / ".claude").mkdir()
    (proj / ".claude" / ".set-version").write_text(old[:8] + "\n")
    ctx = Context(root=str(root), home=str(tmp_path))
    c = deployed_version(ctx, str(proj))
    assert c.status == "warn" and "3 commit(s) behind" in c.detail
    assert c.fix == f"cd {proj} && set-project init"
    (proj / ".claude" / ".set-version").write_text(git(root, "rev-parse", "--short", "HEAD"))
    assert deployed_version(ctx, str(proj)).status == "ok"
    (proj / ".claude" / ".set-version").unlink()
    assert "never deployed" in deployed_version(ctx, str(proj)).detail


def registration(server_dir, project_dir):
    return {"mcpServers": {"set-core": {"type": "stdio", "command": "env", "args": [
        f"CLAUDE_PROJECT_DIR={project_dir}", "uv", "--directory", server_dir, "run", "python", "set_mcp_server.py"]}}}


def test_an_mcp_registration_that_points_elsewhere_warns(machine):
    ctx, tmp = machine
    proj = project_repo(tmp)
    wt = tmp / "proj-wt-feature"
    good = mcp_registration(ctx, {str(proj): registration(ctx.mcp_dir, str(proj))}, str(proj))
    assert good.status == "ok"
    c = mcp_registration(ctx, {str(proj): registration(ctx.mcp_dir, str(wt))}, str(proj))
    assert c.status == "warn" and str(wt) in c.detail and str(proj) in c.detail
    other = mcp_registration(ctx, {str(proj): registration("/elsewhere/mcp-server", str(proj))}, str(proj))
    assert other.status == "warn" and "/elsewhere/mcp-server" in other.detail
    missing = mcp_registration(ctx, {}, str(proj))
    assert missing.status == "warn" and "not registered" in missing.detail


def test_a_data_repository_skips_deploy_mcp_and_bus(machine):
    ctx, tmp = machine
    proj = project_repo(tmp, "corpus")
    checks = check_project(ctx, "corpus", {"path": str(proj), "deploy": False}, {}, {})
    for name in ("deploy", "mcp", "bus"):
        c = by(checks, name)
        assert c.status == "skip" and "data repository" in c.detail
    assert by(checks, "path").status == "ok"
    assert by(checks, "kb").status == "ok", "consumers link to it, so its search is still checked"


def test_a_consumer_is_checked_on_every_count(machine):
    ctx, tmp = machine
    proj = project_repo(tmp)
    checks = check_project(ctx, "proj", {"path": str(proj)}, {}, {})
    assert {c.name for c in checks} == {"path", "deploy", "mcp", "bus", "role", "kb"}
    assert by(checks, "bus").status == "warn" and by(checks, "bus").fix == f"cd {proj} && sac install"


# ── MCP probe ────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not shutil.which("uv") or not (REPO / "mcp-server" / ".venv").is_dir(),
                    reason="needs uv and the MCP server's environment")
def test_the_mcp_server_answers_kb_search():
    ok, detail = probe(str(REPO / "mcp-server"))
    assert ok, detail
    assert "answered kb_search" in detail


def test_a_server_that_cannot_start_fails(tmp_path):
    (tmp_path / "set_mcp_server.py").write_text("import sys; sys.exit(3)\n")
    ok, detail = probe(str(tmp_path), timeout=30)
    assert not ok and detail


# ── tools ────────────────────────────────────────────────────────────────────


def test_a_missing_tool_fails_with_an_install_hint(machine):
    ctx, tmp = machine
    bindir = tmp / "toolbin"
    bindir.mkdir()
    for name in ("python3", "uv", "node", "git", "claude", "openspec"):
        found = shutil.which(name)
        if found:
            (bindir / name).symlink_to(found)
    ctx.env["PATH"] = str(bindir)
    c = by(check_tools(ctx), "jq")
    assert c.status == "fail" and "not on PATH" in c.detail and "apt install jq" in c.fix


# ── end to end, in the sandbox ───────────────────────────────────────────────

SECRET = "SANDBOXSECRET-9f3c1a20e7"


def sandbox_env(machine) -> dict:
    ctx, tmp = machine
    cfg = Path(ctx.env["SET_CONFIG_DIR"])
    (cfg / "providers.json").write_text(json.dumps({
        "version": 1, "default": {"provider": "glm", "model": "glm-x"},
        "providers": {"glm": {"models": ["glm-x"], "requires_credential": True, "default_model": "glm-x",
                              "credential": {"token": SECRET, "base_url": "https://example.invalid/api"},
                              "env": {}, "args": []}}}))
    os.chmod(cfg / "providers.json", 0o600)
    proj = project_repo(tmp, "consumer")
    (cfg / "projects.json").write_text(json.dumps({"projects": {
        "consumer": {"path": str(proj)}, "gone": {"path": str(tmp / "gone")}}}))
    return {**ctx.env, "GH_CONFIG_DIR": str(tmp / "gh"), "SET_AGENT_COMM_DIR": str(tmp / "bus"),
            "XDG_DATA_HOME": str(tmp / "data")}


def run_doctor(env, *args):
    return subprocess.run([sys.executable, str(REPO / "bin" / "set-doctor"), "--offline", *args], env=env,
                          capture_output=True, text=True, timeout=300)


def test_end_to_end_json_contract_and_no_secret(machine):
    env = sandbox_env(machine)
    r = run_doctor(env, "--json")
    assert SECRET not in r.stdout and SECRET not in r.stderr
    d = json.loads(r.stdout)
    assert d["schema"] == "set-doctor/1"
    assert d["ok"] is (r.returncode == 0), "ok mirrors the exit code; the sandbox may or may not have a fail"
    checks = d["checks"]
    assert {c["section"] for c in checks} >= {"install", "checkout", "tools", "mcp", "bus", "project",
                                               "providers", "github"}
    assert not [c for c in checks if c.get("project") == "gone"], "a stale entry is not checked as a project"
    [stale] = [c for c in checks if c["name"] == "stale"]
    assert stale["status"] == "warn" and "gone" in stale["detail"] and "set-project remove" in stale["fix"]
    glm = [c for c in checks if c["name"] == "glm"][0]
    assert glm["status"] == "ok" and "credential present" in glm["detail"]
    assert all("fix" in c for c in checks if c["status"] in ("warn", "fail")), "every problem names its fix"
    assert sum(d["counts"].values()) == len(checks)


def test_end_to_end_text_names_the_fix_and_the_project(machine):
    env = sandbox_env(machine)
    r = run_doctor(env, "--project", "gone")
    assert SECRET not in r.stdout
    assert "WARN  stale" in r.stdout and "gone: gone" in r.stdout and 'set-project remove "$p"' in r.stdout
    assert "consumer" not in r.stdout.split("PROJECTS", 1)[1].split("PROVIDERS", 1)[0], "--project filters"


def test_a_refused_provider_file_is_not_called_absent(machine):
    env = sandbox_env(machine)
    os.chmod(Path(env["SET_CONFIG_DIR"]) / "providers.json", 0o664)
    d = json.loads(run_doctor(env, "--json", "--project", "none").stdout)
    [glm] = [c for c in d["checks"] if c["name"] == "glm"]
    assert glm["status"] == "fail" and "refused" in glm["detail"] and "chmod 600" in glm["detail"]
    assert "not configured" not in glm["detail"]


def test_an_old_node_fails_with_its_reason(machine):
    ctx, tmp = machine
    bindir = tmp / "oldnode"
    bindir.mkdir()
    (bindir / "node").write_text("#!/bin/sh\necho v12.22.9\n")
    (bindir / "node").chmod(0o755)
    ctx.env["PATH"] = f"{bindir}:{ctx.env['PATH']}"
    c = by(check_tools(ctx), "node")
    assert c.status == "fail" and "v12.22.9" in c.detail and "Claude Code needs 18" in c.detail


# ── archived registry entries (fleet-era-consolidation) ──────────────────────


def test_archived_entries_are_left_out_of_a_full_run():
    reg = {"a": {"path": "/x"}, "b": {"path": "/y", "archived": True}, "c": {"path": "/z", "archived": True},
           "d": {"path": "/w", "archived": False}}
    names, archived = archived_entries(reg, sorted(reg), None)
    assert names == ["a", "d"] and archived == ["b", "c"]
    c = archived_check(archived)
    assert c.status == "skip" and c.detail.startswith("2 archived projects skipped")


def test_three_archived_entries_make_one_summary_line():
    c = archived_check(["x", "y", "z"])
    assert c.name == "archived" and c.detail.startswith("3 archived projects skipped") and c.project is None


def test_an_archived_project_asked_for_by_name_is_checked():
    reg = {"old": {"path": "/x", "archived": True}}
    names, archived = archived_entries(reg, ["old"], "old")
    assert names == ["old"] and archived == []


def test_end_to_end_an_archived_entry_is_not_checked(machine):
    env = sandbox_env(machine)
    ctx, tmp = machine
    cfg = Path(ctx.env["SET_CONFIG_DIR"])
    reg = json.loads((cfg / "projects.json").read_text())
    reg["projects"]["shelved"] = {"path": str(project_repo(tmp, "shelved")), "archived": True}
    (cfg / "projects.json").write_text(json.dumps(reg))
    d = json.loads(run_doctor(env, "--json").stdout)
    assert not [c for c in d["checks"] if c.get("project") == "shelved"]
    [a] = [c for c in d["checks"] if c["name"] == "archived"]
    assert a["status"] == "skip" and a["detail"].startswith("1 archived project skipped")
    d = json.loads(run_doctor(env, "--json", "--project", "shelved").stdout)
    assert [c for c in d["checks"] if c.get("project") == "shelved"], "asked for by name, it is checked"
