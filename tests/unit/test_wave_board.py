"""set-wave-board and set-hook-waveboard — the wave-board capability.

Every test runs the real executables against throwaway git repositories, with the set-core
registry replaced through SET_CORE_REGISTRY, so nothing here reads this machine's projects.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "bin" / "set-wave-board"
HOOK = REPO / "bin" / "set-hook-waveboard"
DEPLOY = REPO / "bin" / "set-deploy-hooks"
URL = "https://claude.ai/code/artifact/00000000-0000-0000-0000-000000000000"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}).stdout


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "commit", "-q", "--allow-empty", "-m", "init")
    return path


@pytest.fixture
def env(tmp_path, monkeypatch):
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"projects": {}}))
    e = {**os.environ, "SET_CORE_REGISTRY": str(reg), "SET_WAVEBOARD_BY": "test-host"}
    e.pop("SET_WAVEBOARD_PUSH", None)
    e.pop("SET_WAVEBOARD_NAG_SECONDS", None)
    return e


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path / "consumer")


def run(env, repo, *args, check=True):
    r = subprocess.run([str(TOOL), *args[:1], "--repo", str(repo), *args[1:]], env=env,
                       capture_output=True, text=True, timeout=60)
    if check:
        assert r.returncode == 0, r.stderr
    return r


def job_file(repo, job="j"):
    return json.loads((repo / "docs" / "waveboard" / f"{job}.json").read_text())


def status(repo, item, job="j"):
    for w in job_file(repo, job)["waves"]:
        for it in w["items"]:
            if it["id"] == item:
                return it["status"]
    raise KeyError(item)


def new_job(env, repo, *items):
    """items: (item_id, evidence-dict-or-None)."""
    run(env, repo, "init", "j", "--title", "A job")
    for item_id, ev in items:
        extra = ["--evidence", json.dumps(ev)] if ev else []
        run(env, repo, "add", "j", "--wave", "w0", "--item", item_id, "--title", item_id.upper(), *extra)


def write_tasks(path: Path, checked: int, total: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"- [{'x' if i < checked else ' '}] {i + 1}.1 task\n" for i in range(total)))


# ── job file ─────────────────────────────────────────────────────────────────

def test_init_and_add_create_the_job_file(env, repo):
    new_job(env, repo, ("a", None))
    data = job_file(repo)
    assert data["schema"] == "set-wave-board/1"
    assert data["artifact_url"] is None
    assert data["waves"][0]["id"] == "w0"
    assert data["waves"][0]["items"][0]["status"] == "todo"
    assert data["waves"][0]["items"][0]["by"] == "test-host"


@pytest.mark.parametrize("ev", [
    {"type": "nope"},
    {"type": "path-exists"},
    {"type": "path-exists", "path": "/etc/passwd"},
    {"type": "path-exists", "path": "../outside"},
    {"type": "project", "project": "x", "evidence": {"type": "project", "project": "y",
                                                       "evidence": {"type": "path-exists", "path": "a"}}},
])
def test_malformed_evidence_is_refused_and_nothing_changes(env, repo, ev):
    new_job(env, repo)
    before = (repo / "docs" / "waveboard" / "j.json").read_text()
    r = run(env, repo, "add", "j", "--wave", "w0", "--item", "a", "--title", "A",
            "--evidence", json.dumps(ev), check=False)
    assert r.returncode == 2
    assert (repo / "docs" / "waveboard" / "j.json").read_text() == before


# ── evidence ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("checked,total,expected", [(0, 3, "todo"), (1, 3, "doing"), (3, 3, "done")])
def test_openspec_tasks_evidence(env, repo, checked, total, expected):
    write_tasks(repo / "openspec/changes/c1/tasks.md", checked, total)
    new_job(env, repo, ("a", {"type": "openspec-tasks", "path": "openspec/changes/c1/tasks.md"}))
    run(env, repo, "sync")
    assert status(repo, "a") == expected


def test_an_archived_change_counts_as_done(env, repo):
    write_tasks(repo / "openspec/changes/archive/2026-10-01-c1/tasks.md", 1, 2)
    new_job(env, repo, ("a", {"type": "openspec-tasks", "path": "openspec/changes/c1/tasks.md"}))
    run(env, repo, "sync")
    assert status(repo, "a") == "done"


def test_path_exists_and_commit_evidence(env, repo):
    new_job(env, repo, ("p", {"type": "path-exists", "path": "out/report.txt"}),
            ("c", {"type": "commit", "grep": "wave-item-c"}))
    run(env, repo, "sync")
    assert (status(repo, "p"), status(repo, "c")) == ("todo", "todo")
    (repo / "out").mkdir()
    (repo / "out/report.txt").write_text("x")
    git(repo, "commit", "-q", "--allow-empty", "-m", "fix: wave-item-c landed")
    run(env, repo, "sync")
    assert (status(repo, "p"), status(repo, "c")) == ("done", "done")


def test_absence_of_evidence_leaves_a_manual_status(env, repo):
    new_job(env, repo, ("p", {"type": "path-exists", "path": "not/yet"}))
    run(env, repo, "set", "j", "p", "doing")
    run(env, repo, "sync")
    assert status(repo, "p") == "doing"


# ── precedence ───────────────────────────────────────────────────────────────

def test_evidence_corrects_a_premature_done(env, repo):
    write_tasks(repo / "openspec/changes/c1/tasks.md", 1, 2)
    new_job(env, repo, ("a", {"type": "openspec-tasks", "path": "openspec/changes/c1/tasks.md"}))
    r = run(env, repo, "set", "j", "a", "done")
    assert status(repo, "a") == "doing"
    assert "evidence says doing" in r.stderr


@pytest.mark.parametrize("manual", ["blocked", "skipped"])
def test_blocked_and_skipped_survive_evidence(env, repo, manual):
    (repo / "here").write_text("x")
    new_job(env, repo, ("a", {"type": "path-exists", "path": "here"}))
    run(env, repo, "set", "j", "a", manual, "--note", "decided by a person")
    run(env, repo, "sync")
    assert status(repo, "a") == manual
    assert job_file(repo)["waves"][0]["items"][0]["note"] == "decided by a person"


# ── cross-project evidence ───────────────────────────────────────────────────

def test_project_evidence_resolves_through_the_registry(env, repo, tmp_path):
    other = make_repo(tmp_path / "other")
    (other / "done.flag").write_text("x")
    Path(env["SET_CORE_REGISTRY"]).write_text(json.dumps({"projects": {"other": {"path": str(other)}}}))
    new_job(env, repo, ("a", {"type": "project", "project": "other",
                              "evidence": {"type": "path-exists", "path": "done.flag"}}))
    run(env, repo, "sync")
    assert status(repo, "a") == "done"
    assert str(tmp_path) not in (repo / "docs/waveboard/j.json").read_text()


def test_an_unregistered_project_is_reported_and_left_alone(env, repo):
    new_job(env, repo, ("a", {"type": "project", "project": "elsewhere",
                              "evidence": {"type": "path-exists", "path": "x"}}))
    run(env, repo, "set", "j", "a", "doing")
    r = run(env, repo, "sync", "--json")
    assert status(repo, "a") == "doing"
    [res] = json.loads(r.stdout)
    assert res["unresolved"] and res["unresolved"][0]["item"] == "a"
    assert "UNRESOLVED" in r.stderr


# ── sync, payload, push cycle ────────────────────────────────────────────────

def test_sync_is_idempotent_and_the_push_cycle_closes(env, repo):
    new_job(env, repo, ("a", {"type": "path-exists", "path": "f"}))
    run(env, repo, "link", "j", URL)
    first = run(env, repo, "sync")
    assert first.stdout.startswith(f"PUSH j {URL} ")
    payload = repo / ".set/waveboard/j.state.json"
    state = json.loads(payload.read_text())
    assert set(state) == {"schema", "job", "title", "waves", "synced_at", "synced_by", "content_hash"}

    job_mtime, payload_mtime = (repo / "docs/waveboard/j.json").stat().st_mtime_ns, payload.stat().st_mtime_ns
    time.sleep(0.02)
    second = json.loads(run(env, repo, "sync", "--json").stdout)[0]
    assert not second["file_changed"] and not second["state_changed"]
    assert (repo / "docs/waveboard/j.json").stat().st_mtime_ns == job_mtime
    assert payload.stat().st_mtime_ns == payload_mtime

    assert "PENDING j" in run(env, repo, "pending").stdout
    run(env, repo, "pushed", "j", "--version", "3")
    assert json.loads((repo / ".set/waveboard/j.pushed.json").read_text())["version"] == 3
    assert run(env, repo, "pending").stdout == ""
    assert run(env, repo, "sync").stdout == ""

    (repo / "f").write_text("x")
    third = run(env, repo, "sync")
    assert third.stdout.startswith("PUSH j")
    assert status(repo, "a") == "done"
    # machine-local state never shows up as untracked
    assert ".set" not in git(repo, "status", "--porcelain")


def test_render_embeds_the_state_as_seed(env, repo, tmp_path):
    new_job(env, repo, ("a", None))
    out = tmp_path / "board.html"
    run(env, repo, "render", "j", "-o", str(out))
    html = out.read_text()
    assert html.startswith("<!doctype html>")
    seed = html.split('<script type="application/json" id="seed">', 1)[1].split("</script>", 1)[0]
    assert json.loads(seed)["job"] == "j"
    bare = tmp_path / "bare.html"
    run(env, repo, "render", "j", "-o", str(bare), "--bare")
    assert bare.read_text().startswith("<title>")
    assert Path(run(env, repo, "page").stdout.strip()).is_file()


def test_render_names_the_page_after_the_job(env, repo, tmp_path):
    # The <title> names the published artifact; a generic one makes every board look alike.
    new_job(env, repo, ("a", None))
    run(env, repo, "init", "k", "--title", "Plan <A&B>")
    out = tmp_path / "k.html"
    run(env, repo, "render", "k", "-o", str(out), "--bare")
    assert out.read_text().startswith("<title>Plan &lt;A&amp;B&gt; · Wave Board</title>")


# ── the Stop hook ────────────────────────────────────────────────────────────

def hook(env, cwd, event=None, **extra_env):
    return subprocess.run([str(HOOK)], input=json.dumps({"cwd": str(cwd), **(event or {})}),
                          env={**env, **extra_env}, capture_output=True, text=True, timeout=60)


def pending_repo(env, repo):
    new_job(env, repo, ("a", None))
    run(env, repo, "link", "j", URL)


def test_hook_blocks_once_then_backs_off(env, repo):
    pending_repo(env, repo)
    r = hook(env, repo)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "block"
    for needle in ("ArtifactData", URL, "collection=board", "doc_id=state",
                   str(repo / ".set/waveboard/j.state.json"), "set-wave-board pushed j"):
        assert needle in out["reason"]
    assert "if_version=" not in out["reason"].split("Job `j`")[1].split("2.")[0]
    again = hook(env, repo)
    assert again.returncode == 0 and again.stdout == ""


def test_hook_pins_the_recorded_version(env, repo):
    pending_repo(env, repo)
    run(env, repo, "sync")
    run(env, repo, "pushed", "j", "--version", "7")
    run(env, repo, "set", "j", "a", "doing")
    out = json.loads(hook(env, repo).stdout)
    assert "if_version=7" in out["reason"]


@pytest.mark.parametrize("event,extra", [
    ({"stop_hook_active": True}, {}),
    ({}, {"SET_WAVEBOARD_PUSH": "off"}),
])
def test_hook_is_silent_on_its_own_continuation_and_when_off(env, repo, event, extra):
    pending_repo(env, repo)
    r = hook(env, repo, event, **extra)
    assert r.returncode == 0 and r.stdout == ""


def test_hook_is_silent_without_a_board_or_a_repo(env, repo, tmp_path):
    assert hook(env, repo).stdout == ""
    plain = tmp_path / "plain"
    plain.mkdir()
    assert hook(env, plain).stdout == ""


def test_hook_is_silent_in_a_linked_worktree(env, repo, tmp_path):
    pending_repo(env, repo)
    git(repo, "add", "docs")
    git(repo, "commit", "-q", "-m", "board")
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt))
    assert hook(env, wt).stdout == ""
    assert json.loads(hook(env, wt, SET_WAVEBOARD_PUSH="worktree").stdout)["decision"] == "block"


# ── deployment ───────────────────────────────────────────────────────────────

@pytest.mark.skipif(shutil.which("jq") is None, reason="set-deploy-hooks requires jq")
def test_deploy_adds_the_hook_once_and_keeps_project_hooks(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    settings = proj / ".claude" / "settings.json"
    settings.write_text(json.dumps({"hooks": {
        "UserPromptSubmit": [{"matcher": "", "hooks": [
            {"type": "command", "command": "set-hook-skill", "timeout": 5}]}],
        "PreToolUse": [{"matcher": "Skill", "hooks": [
            {"type": "command", "command": "set-hook-activity", "timeout": 5}]}],
        "Stop": [{"matcher": "", "hooks": [
            {"type": "command", "command": "set-hook-stop", "timeout": 5},
            {"type": "command", "command": "my-project-stop-hook"}]}],
    }}, indent=2))

    def stop_commands():
        data = json.loads(settings.read_text())
        return [h["command"] for e in data["hooks"]["Stop"] for h in e["hooks"]]

    for _ in range(2):
        subprocess.run([str(DEPLOY), "--quiet", str(proj)], check=True, capture_output=True, timeout=60)
        cmds = stop_commands()
        assert cmds.count("set-hook-waveboard") == 1
        assert "my-project-stop-hook" in cmds
        assert cmds.count("set-hook-stop") == 1

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    subprocess.run([str(DEPLOY), "--quiet", str(fresh)], check=True, capture_output=True, timeout=60)
    assert "set-hook-waveboard" in (fresh / ".claude/settings.json").read_text()


def test_install_links_both_commands():
    text = (REPO / "install.sh").read_text()
    scripts_line = next(line for line in text.splitlines() if "local scripts=(" in line)
    assert " set-wave-board" in scripts_line and " set-hook-waveboard" in scripts_line
    for p in (TOOL, HOOK):
        assert os.access(p, os.X_OK)
