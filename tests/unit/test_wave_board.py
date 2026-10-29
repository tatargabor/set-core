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
    for var in ("SET_WAVEBOARD_PUSH", "SET_WAVEBOARD_NAG_SECONDS", "SET_WAVEBOARD_REVIEW",
                "SET_WAVEBOARD_REVIEW_SECONDS", "SET_WAVEBOARD_STALE_COMMITS"):
        e.pop(var, None)
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
    assert "by" not in data["waves"][0]["items"][0]


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
    assert set(state) == {"schema", "job", "title", "assignees", "waves", "synced_at", "synced_by", "content_hash"}

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


def test_render_carries_the_kanban_view(env, repo, tmp_path):
    # The behaviour (columns, filter, persistence, live update) is checked in a browser; this
    # pins the parts a careless edit would drop: both views, the guarded storage key, the
    # column order, the skipped strip, the hidden-blocked notice, and that the page writes only
    # its own documents, never the agent's board/state.
    new_job(env, repo, ("a", None))
    out = tmp_path / "board.html"
    run(env, repo, "render", "j", "-o", str(out))
    html = out.read_text()
    assert 'data-view="waves"' in html and 'data-view="kanban"' in html
    assert 'var COLUMNS = ["todo", "doing", "blocked", "done"];' in html
    storage = [l.strip() for l in html.splitlines() if "localStorage" in l]
    assert len(storage) == 2, storage  # one read, one write — and both inside try
    for line in storage:
        assert line.startswith("try {"), line
    assert 'VIEW_KEY = "waveboard.view"' in html
    assert '"skipped-strip"' in html
    assert "blocked outside this filter" in html
    assert "[hidden] { display: none !important; }" in html
    script = html.split('<script>', 1)[1]
    assert 'picksDoc = db.doc("board/assignees");' in script
    # The page writes only its own documents (assignee, status and answer picks), each through
    # its own handle; nothing else in the script may write, and board/state never.
    own = ("picksDoc.", "statusesDoc.", "answersDoc.")
    others = "\n".join(l for l in script.splitlines()
                       if not any(h in l for h in own) and "classList." not in l)  # CSS classes, not data
    for write in (".set(", ".update(", ".add(", ".delete("):
        assert write not in others, write


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


# ── staleness: the items only an agent can move (change wave-board-staleness) ──
#
# Dates are pinned: the board's `updated` stamps are moved into the past and every commit
# carries an explicit committer date, so "commits since the change" never depends on how
# many commits land inside one wall-clock second.

PAST = "2026-01-01T00:00:00Z"


@pytest.fixture
def srepo(tmp_path):
    """A repository whose only commit predates PAST, so it never counts as work."""
    path = tmp_path / "consumer"
    path.mkdir()
    git(path, "init", "-q")
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=path, check=True,
                   capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
                        "GIT_AUTHOR_DATE": "2025-12-01T00:00:00Z",
                        "GIT_COMMITTER_DATE": "2025-12-01T00:00:00Z"})
    return path


def backdate(srepo, when=PAST, job="j"):
    data = job_file(srepo, job)
    for w in data["waves"]:
        for it in w["items"]:
            it["updated"] = when
    (srepo / "docs" / "waveboard" / f"{job}.json").write_text(json.dumps(data, indent=2) + "\n")


def commit_at(srepo, day: int, n: int = 1):
    """`n` empty commits dated 2026-01-<day>, after PAST and before now."""
    for i in range(n):
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", f"work {day}.{i}"], cwd=srepo,
                       check=True, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
                            "GIT_AUTHOR_DATE": f"2026-01-{day:02d}T12:00:{i:02d}Z",
                            "GIT_COMMITTER_DATE": f"2026-01-{day:02d}T12:00:{i:02d}Z"})


def stale(env, srepo, job="j"):
    return {r["job"]: r for r in json.loads(run(env, srepo, "stale", "--json").stdout)}[job]


def stale_repo(env, srepo, commits=3):
    new_job(env, srepo, ("a", None))
    backdate(srepo)
    commit_at(srepo, 2, commits)


def test_commits_after_the_change_make_a_board_with_manual_items_stale(env, srepo):
    """AC-1."""
    stale_repo(env, srepo)
    r = stale(env, srepo)
    assert r["commits_since_change"] == 3
    assert [m["id"] for m in r["manual_open"]] == ["a"]
    assert r["manual_open"][0]["status"] == "todo" and r["manual_open"][0]["wave"] == "w0"
    assert r["stale"] is True
    assert r["last_change"] == PAST


def test_the_boards_own_commit_is_not_enough(env, srepo):
    """AC-2: the commit recording a manual `set` is itself newer than the stamp."""
    new_job(env, srepo, ("a", None))
    backdate(srepo)
    git(srepo, "add", "docs")
    commit_at(srepo, 2)
    r = stale(env, srepo)
    assert r["commits_since_change"] == 1 and r["stale"] is False


def test_only_items_sync_cannot_move_are_manual(env, srepo):
    """AC-3."""
    missing = {"type": "path-exists", "path": "not-yet"}
    new_job(env, srepo, ("t", None), ("b", missing), ("d", missing), ("x", None))
    run(env, srepo, "set", "j", "b", "blocked")
    run(env, srepo, "set", "j", "d", "doing")
    run(env, srepo, "set", "j", "x", "done")
    assert [m["id"] for m in stale(env, srepo)["manual_open"]] == ["t", "b"]


def test_a_board_whose_items_all_have_evidence_is_never_stale(env, srepo):
    """AC-4."""
    new_job(env, srepo, ("d", {"type": "path-exists", "path": "not-yet"}))
    run(env, srepo, "set", "j", "d", "doing")
    backdate(srepo)
    commit_at(srepo, 2, 5)
    r = stale(env, srepo)
    assert r["commits_since_change"] == 5 and r["manual_open"] == [] and r["stale"] is False


def test_not_measurable_is_null_not_zero(env, srepo):
    """AC-5."""
    d = srepo / "docs" / "waveboard"
    d.mkdir(parents=True)
    (d / "j.json").write_text(json.dumps({"schema": "set-wave-board/1", "job": "j", "title": "J",
                                          "artifact_url": None, "waves": [{"id": "w0", "items": [
                                              {"id": "a", "title": "A", "status": "todo",
                                               "evidence": None}]}]}))
    commit_at(srepo, 2, 5)
    r = stale(env, srepo)
    assert r["commits_since_change"] is None and r["stale"] is False


def test_without_any_stamp_the_created_date_is_the_last_change(env, srepo):
    """D2: no item `updated` and no `reviewed` — `created`, read as midnight UTC."""
    d = srepo / "docs" / "waveboard"
    d.mkdir(parents=True)
    (d / "j.json").write_text(json.dumps({"schema": "set-wave-board/1", "job": "j", "title": "J",
                                          "artifact_url": None, "created": "2026-01-01",
                                          "waves": [{"id": "w0", "items": [
                                              {"id": "a", "title": "A", "status": "todo",
                                               "evidence": None}]}]}))
    commit_at(srepo, 2, 3)
    r = stale(env, srepo)
    assert r["last_change"] == PAST and r["commits_since_change"] == 3 and r["stale"] is True


def test_a_review_resets_staleness(env, srepo):
    """AC-6."""
    stale_repo(env, srepo)
    assert stale(env, srepo)["stale"] is True
    run(env, srepo, "reviewed", "j")
    r = stale(env, srepo)
    assert r["commits_since_change"] == 0 and r["stale"] is False
    assert job_file(srepo)["reviewed"]["by"] == "test-host"


def test_a_review_does_not_cause_a_push(env, srepo):
    """AC-7."""
    new_job(env, srepo, ("a", None))
    run(env, srepo, "link", "j", URL)
    run(env, srepo, "sync")
    run(env, srepo, "pushed", "j", "--version", "1")
    run(env, srepo, "reviewed", "j")
    run(env, srepo, "sync")
    assert json.loads(run(env, srepo, "pending", "--json").stdout) == []
    assert "reviewed" in job_file(srepo)


def test_the_threshold_comes_from_the_environment(env, srepo):
    stale_repo(env, srepo, commits=2)
    assert stale(env, srepo)["stale"] is False
    env2 = {**env, "SET_WAVEBOARD_STALE_COMMITS": "2"}
    assert stale(env2, srepo)["stale"] is True


def test_hook_asks_for_a_review_of_a_stale_board(env, srepo):
    """AC-8: no page URL, so this is the review alone."""
    stale_repo(env, srepo)
    out = json.loads(hook(env, srepo).stdout)
    assert out["decision"] == "block"
    reason = out["reason"]
    for needle in ("Wave board review", "3 commit(s)", "- a [todo] A",
                   "set-wave-board set j <item>", "set-wave-board reviewed j"):
        assert needle in reason, needle
    assert "ArtifactData" not in reason


def test_the_review_backs_off_on_its_own_clock(env, srepo):
    """AC-9."""
    stale_repo(env, srepo)
    assert hook(env, srepo).stdout != ""
    assert hook(env, srepo).stdout == ""
    assert (srepo / ".set" / "waveboard" / "j.review-nag").is_file()
    assert json.loads(hook(env, srepo, SET_WAVEBOARD_REVIEW_SECONDS="0").stdout)["decision"] == "block"


def test_push_and_review_due_together_make_one_block(env, srepo):
    """AC-10."""
    stale_repo(env, srepo)
    run(env, srepo, "link", "j", URL)
    r = hook(env, srepo)
    blocks = [line for line in r.stdout.splitlines() if line.strip()]
    assert len(blocks) == 1
    reason = json.loads(blocks[0])["reason"]
    assert reason.index("ArtifactData") < reason.index("Wave board review")


def test_the_review_alone_can_be_switched_off(env, srepo):
    """AC-11."""
    stale_repo(env, srepo)
    assert hook(env, srepo, SET_WAVEBOARD_REVIEW="off").stdout == ""


def test_the_review_is_skipped_in_a_linked_worktree(env, srepo, tmp_path):
    """AC-12."""
    stale_repo(env, srepo)
    git(srepo, "add", "docs")
    commit_at(srepo, 1)
    commit_at(srepo, 3, 3)
    wt = tmp_path / "wt"
    git(srepo, "worktree", "add", "-q", str(wt))
    assert stale(env, wt)["stale"] is True
    assert hook(env, wt).stdout == ""


def test_the_review_lists_at_most_twenty_items(env, srepo):
    new_job(env, srepo, *[(f"i{n:02d}", None) for n in range(22)])
    backdate(srepo)
    commit_at(srepo, 2, 3)
    reason = json.loads(hook(env, srepo).stdout)["reason"]
    assert "- i19 [todo]" in reason and "- i20 [todo]" not in reason
    assert "+2 more" in reason


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


# ── assignees ────────────────────────────────────────────────────────────────

def test_assignees_and_assign_reach_the_payload(env, repo):
    new_job(env, repo, ("a", None))
    run(env, repo, "assignees", "j", "András, Gábor,András")
    run(env, repo, "assign", "j", "a", "Gábor")
    data = job_file(repo)
    assert data["assignees"] == ["András", "Gábor"]
    assert data["waves"][0]["items"][0]["assignee"] == "Gábor"
    run(env, repo, "sync")
    state = json.loads((repo / ".set/waveboard/j.state.json").read_text())
    assert state["assignees"] == ["András", "Gábor"]
    assert state["waves"][0]["items"][0]["assignee"] == "Gábor"
    run(env, repo, "assign", "j", "a", "-")
    assert job_file(repo)["waves"][0]["items"][0]["assignee"] is None


def test_assign_unknown_item_is_a_usage_error(env, repo):
    new_job(env, repo, ("a", None))
    r = run(env, repo, "assign", "j", "nope", "Gábor", check=False)
    assert r.returncode != 0


def test_a_legacy_machine_name_never_reaches_the_payload(env, repo):
    new_job(env, repo, ("a", None))
    p = repo / "docs/waveboard/j.json"
    data = json.loads(p.read_text())
    data["waves"][0]["items"][0]["by"] = "some-laptop"
    p.write_text(json.dumps(data))
    run(env, repo, "sync")
    assert "some-laptop" not in p.read_text()
    assert "some-laptop" not in (repo / ".set/waveboard/j.state.json").read_text()


# ── waits: decisions and blockers ────────────────────────────────────────────

def waits(repo, item="a"):
    for w in job_file(repo)["waves"]:
        for it in w["items"]:
            if it["id"] == item:
                return it.get("waits")
    raise KeyError(item)


def test_wait_records_a_decision_and_a_blocker_and_reaches_the_payload(env, repo):
    new_job(env, repo, ("a", None))
    run(env, repo, "assignees", "j", "András,Gábor")
    run(env, repo, "wait", "j", "a", "--decision", "Free hour or  package price?", "--who", "Gábor", "--ref", "G3")
    run(env, repo, "wait", "j", "a", "--blocker", "Run migration 0019", "--who", "Gábor")
    assert waits(repo) == [
        {"kind": "decision", "who": "Gábor", "text": "Free hour or package price?", "ref": "G3"},
        {"kind": "blocker", "who": "Gábor", "text": "Run migration 0019", "ref": None},
    ]
    assert status(repo, "a") == "todo"  # a wait does not change the status
    run(env, repo, "sync")
    state = json.loads((repo / ".set/waveboard/j.state.json").read_text())
    assert len(state["waves"][0]["items"][0]["waits"]) == 2


def test_the_same_ref_replaces_and_unwait_clears(env, repo):
    new_job(env, repo, ("a", None))
    run(env, repo, "wait", "j", "a", "--decision", "first", "--who", "Gábor", "--ref", "G1")
    run(env, repo, "wait", "j", "a", "--decision", "second", "--who", "Gábor", "--ref", "G1")
    run(env, repo, "wait", "j", "a", "--blocker", "other", "--ref", "B1")
    assert [w["text"] for w in waits(repo)] == ["second", "other"]
    assert run(env, repo, "unwait", "j", "a", check=False).returncode == 2  # two waits: say which
    run(env, repo, "unwait", "j", "a", "--ref", "G1")
    assert [w["ref"] for w in waits(repo)] == ["B1"]
    run(env, repo, "unwait", "j", "a")
    assert waits(repo) is None


def test_wait_refuses_empty_text_and_unknown_items(env, repo):
    new_job(env, repo, ("a", None))
    assert run(env, repo, "wait", "j", "a", "--decision", "  ", check=False).returncode == 2
    assert run(env, repo, "wait", "j", "nope", "--blocker", "x", check=False).returncode == 2
    assert run(env, repo, "wait", "j", "a", "x", check=False).returncode == 2  # kind is required
    assert run(env, repo, "unwait", "j", "a", "--ref", "G9", check=False).returncode == 2


def test_render_carries_the_waiting_panel_and_a_pill_column_that_fits(env, repo, tmp_path):
    # Behaviour is checked in a browser; this pins what a careless edit would drop: the panel,
    # both wait kinds, and a status column sized by its content instead of a fixed width
    # (a 96px column let "in progress" hang out of its pill).
    new_job(env, repo, ("a", None))
    out = tmp_path / "board.html"
    run(env, repo, "render", "j", "-o", str(out))
    html = out.read_text()
    assert 'id="waiting"' in html and "function renderWaiting" in html and "function ticket(" in html
    assert 'decision: "decision", blocker: "blocker"' in html
    assert "grid-template-columns: subgrid" in html
    assert "96px minmax" not in html


# ── page writes: statuses and answers come back through import ───────────────

def item_of(repo, item="a"):
    for w in job_file(repo)["waves"]:
        for it in w["items"]:
            if it["id"] == item:
                return it
    raise KeyError(item)


def test_wait_options_and_answer(env, repo):
    new_job(env, repo, ("a", None))
    run(env, repo, "wait", "j", "a", "--decision", "Which one?", "--ref", "P1", "--options", "E, C,D")
    assert item_of(repo)["waits"][0]["options"] == ["E", "C", "D"]
    run(env, repo, "answer", "j", "a", "--ref", "P1", "C")
    w = item_of(repo)["waits"][0]
    assert w["answer"] == "C" and w["answered"]
    assert run(env, repo, "answer", "j", "a", "--ref", "X", "C", check=False).returncode == 2


def write_page_docs(d: Path, statuses=None, answers=None):
    (d / "board").mkdir(parents=True, exist_ok=True)
    if statuses is not None:
        (d / "board" / "statuses.json").write_text(json.dumps({"id": "statuses", "data": statuses, "version": 3}))
    if answers is not None:
        (d / "board" / "answers.json").write_text(json.dumps(answers))


def test_import_applies_newer_page_choices_only(env, repo, tmp_path):
    new_job(env, repo, ("a", None), ("b", None))
    run(env, repo, "wait", "j", "a", "--decision", "Go?", "--ref", "G1", "--options", "Igen,Nem")
    run(env, repo, "wait", "j", "b", "--blocker", "Key needed")
    d = tmp_path / "page"
    write_page_docs(d,
                    statuses={"a": {"status": "done", "at": "2999-01-01T00:00:00Z"},
                              "b": {"status": "doing", "at": "2000-01-01T00:00:00Z"}},  # older than b
                    answers={"a|G1": {"answer": "Igen", "at": "2999-01-01T00:00:00Z"},
                             "b|#0": {"answer": "Megvan", "at": "2999-01-01T00:00:00Z"}})
    r = run(env, repo, "import", "j", "--dir", str(d))
    assert "STATUS a todo -> done" in r.stdout and "ANSWER a G1: Igen" in r.stdout
    assert status(repo, "a") == "done" and status(repo, "b") == "todo"
    assert item_of(repo, "a")["waits"][0]["answer"] == "Igen"
    assert item_of(repo, "b")["waits"][0]["answer"] == "Megvan"
    # a second import of the same documents changes nothing
    assert "nothing new from the page" in run(env, repo, "import", "j", "--dir", str(d)).stdout


def test_lang_reaches_the_payload_only_when_set(env, repo):
    new_job(env, repo, ("a", None))
    run(env, repo, "sync")
    state = json.loads((repo / ".set/waveboard/j.state.json").read_text())
    assert "lang" not in state
    run(env, repo, "lang", "j", "hu")
    state = json.loads((repo / ".set/waveboard/j.state.json").read_text())
    assert state["lang"] == "hu"


def test_render_carries_status_picks_answers_and_hungarian(env, repo, tmp_path):
    new_job(env, repo, ("a", None))
    out = tmp_path / "board.html"
    run(env, repo, "render", "j", "-o", str(out))
    html = out.read_text()
    assert 'db.doc("board/statuses")' in html and 'db.doc("board/answers")' in html
    assert "function statusControl" in html and "function answerBox" in html
    assert 'other: "Egyéb:"' in html and 'doing: "folyamatban"' in html
    # the page's writes never touch the agent's document
    assert 'doc("board/state").set' not in html and "board/state\").update" not in html


def test_render_links_the_waiting_panel_to_the_items(env, repo, tmp_path):
    new_job(env, repo, ("a", None))
    out = tmp_path / "board.html"
    run(env, repo, "render", "j", "-o", str(out))
    html = out.read_text()
    assert "function jumpTo" in html and 'el("a", "jump")' in html
    assert html.count("dataset.item = it.id") == 2  # rows and cards
