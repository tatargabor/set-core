"""fleet-repo-sync: the collector over throwaway repositories, and the deploy hint.

Every repository here is built in tmp_path with a bare remote, so ahead/behind, unpushed
branches and worktrees are measured against real git, not against a mock of it.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

from set_orch.fleet import repo_sync as rs


def git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    return p.stdout


def commit(repo, name, body="x\n", msg="c"):
    (repo / name).write_text(body)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", msg)


@pytest.fixture
def pair(tmp_path):
    """A working repository on `main` tracking a bare remote, both with one commit."""
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(remote), str(work))
    git(work, "checkout", "-q", "-b", "main")
    commit(work, "a.txt")
    git(work, "push", "-q", "-u", "origin", "main")
    return work, remote


def push_from_other_clone(tmp_path, remote, n):
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", "main", str(remote), str(other))
    for i in range(n):
        commit(other, f"o{i}.txt")
    git(other, "push", "-q", "origin", "main")


# ─── one repository's state ────────────────────────────────────────────────

class TestRepoState:
    def test_a_clean_tracked_repo_has_no_problems(self, pair):
        work, _ = pair
        row = rs.repo_state(work, time.time())
        assert (row["branch"], row["ahead"], row["behind"], row["uncommitted"]) == ("main", 0, 0, 0)
        assert row["errors"] == {}
        assert rs.problems(row) == []

    def test_ahead_and_behind_are_counted_and_diverged(self, pair, tmp_path):
        work, remote = pair
        push_from_other_clone(tmp_path, remote, 3)
        git(work, "fetch", "-q")
        commit(work, "b.txt")
        commit(work, "c.txt")
        row = rs.repo_state(work, time.time())
        assert (row["ahead"], row["behind"], row["diverged"]) == (2, 3, True)
        assert "diverged" in rs.problems(row)

    def test_uncommitted_entries_are_counted(self, pair):
        work, _ = pair
        (work / "a.txt").write_text("changed\n")
        (work / "new.txt").write_text("n\n")
        row = rs.repo_state(work, time.time())
        assert (row["uncommitted"], row["untracked"]) == (2, 1)
        assert "uncommitted" in rs.problems(row)

    def test_a_branch_with_no_remote_copy_is_listed(self, pair):
        work, _ = pair
        git(work, "checkout", "-q", "-b", "side")
        for i in range(4):
            commit(work, f"s{i}.txt")
        git(work, "checkout", "-q", "main")
        row = rs.repo_state(work, time.time())
        side = [b for b in row["unpushed_branches"] if b["branch"] == "side"]
        assert side and side[0]["commits"] == 4 and side[0]["current"] is False
        assert "unpushed-branch" in rs.problems(row)

    def test_no_upstream_is_explicit_not_zero(self, tmp_path):
        repo = tmp_path / "solo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        commit(repo, "a.txt")
        row = rs.repo_state(repo, time.time())
        assert row["no_upstream"] is True
        assert row["ahead"] is None and row["behind"] is None
        assert "no-upstream" in rs.problems(row)

    def test_a_failing_git_call_is_a_null_gap_and_a_problem(self, pair, monkeypatch):
        work, _ = pair
        real = rs._git

        def broken(root, *args, **kw):
            if args[:1] == ("status",):
                return False, "", "timed out after 10s"
            return real(root, *args, **kw)

        monkeypatch.setattr(rs, "_git", broken)
        row = rs.repo_state(work, time.time())
        assert row["uncommitted"] is None
        assert row["errors"]["uncommitted"] == "timed out after 10s"
        assert "unreadable" in rs.problems(row)

    def test_a_merged_clean_worktree_is_marked_merged(self, pair, tmp_path):
        work, _ = pair
        wt = tmp_path / "wt-merged"
        git(work, "worktree", "add", "-q", "-b", "done", str(wt))
        row = rs.repo_state(work, time.time())
        [entry] = row["worktrees"]
        assert (entry["branch"], entry["merged"], entry["uncommitted"], entry["missing"]) == \
            ("done", True, 0, False)

    def test_an_unmerged_worktree_is_not_merged(self, pair, tmp_path):
        work, _ = pair
        wt = tmp_path / "wt-open"
        git(work, "worktree", "add", "-q", "-b", "open", str(wt))
        commit(wt, "w.txt")
        [entry] = rs.repo_state(work, time.time())["worktrees"]
        assert entry["merged"] is False

    def test_a_worktree_whose_directory_is_gone_is_missing(self, pair, tmp_path):
        work, _ = pair
        wt = tmp_path / "wt-gone"
        git(work, "worktree", "add", "-q", "-b", "gone", str(wt))
        subprocess.run(["rm", "-rf", str(wt)], check=True)
        [entry] = rs.repo_state(work, time.time())["worktrees"]
        assert entry["missing"] is True

    def test_the_remote_is_carried_as_a_host_never_a_url(self):
        assert rs.remote_host("https://user:tok@github.com/o/r.git") == "github.com"
        assert rs.remote_host("ssh://git@git.example.org:2222/root/r.git") == "git.example.org"
        assert rs.remote_host("git@github.com:o/r.git") == "github.com"
        assert rs.remote_host("/srv/bare/r.git") == "local"

    def test_a_scan_takes_no_index_lock_and_writes_nothing(self, pair):
        work, _ = pair
        (work / "a.txt").write_text("dirty\n")
        before = {p: p.stat().st_mtime_ns for p in (work / ".git").rglob("*") if p.is_file()}
        rs.repo_state(work, time.time())
        after = {p: p.stat().st_mtime_ns for p in (work / ".git").rglob("*") if p.is_file()}
        assert before == after


# ─── the activity window ───────────────────────────────────────────────────

class TestActivityWindow:
    def _old(self, repo, days):
        t = time.time() - days * 86400
        env = dict(os.environ, GIT_COMMITTER_DATE=f"@{int(t)} +0000", GIT_AUTHOR_DATE=f"@{int(t)} +0000",
                   GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        (repo / "old.txt").write_text("o\n")
        subprocess.run(["git", "add", "old.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "old"], cwd=repo, check=True, env=env)

    def _repo(self, tmp_path, name, days_old):
        r = tmp_path / name
        r.mkdir()
        git(r, "init", "-q", "-b", "main")
        self._old(r, days_old)
        return r

    def test_an_old_project_is_left_out_and_counted(self, tmp_path):
        r = self._repo(tmp_path, "old", 90)
        listed, excluded = rs.select_projects([{"name": "old", "path": str(r)}], days=30,
                                              now=time.time(), home=tmp_path, e2e_root=None)
        assert listed == [] and excluded["inactive"] == 1

    def test_session_activity_alone_does_not_list_it(self, tmp_path):
        r = self._repo(tmp_path, "sess", 90)
        tdir = tmp_path / ".claude" / "projects" / str(r).replace("/", "-")
        tdir.mkdir(parents=True)
        (tdir / "s.jsonl").write_text("{}\n")
        listed, ex = rs.select_projects([{"name": "sess", "path": str(r)}], days=30,
                                        now=time.time(), home=tmp_path, e2e_root=None)
        assert listed == [] and ex["inactive"] == 1

    def test_somebody_elses_commit_on_a_remote_branch_lists_it(self, tmp_path):
        r = self._repo(tmp_path, "mine", 90)
        remote = tmp_path / "r.git"
        git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
        git(r, "remote", "add", "origin", str(remote))
        git(r, "push", "-q", "origin", "main")
        other = tmp_path / "colleague"
        git(tmp_path, "clone", "-q", "-b", "main", str(remote), str(other))
        commit(other, "theirs.txt")
        git(other, "push", "-q", "origin", "main")
        git(r, "fetch", "-q")
        listed, _ = rs.select_projects([{"name": "mine", "path": str(r)}], days=30,
                                       now=time.time(), home=tmp_path, e2e_root=None)
        assert [p["name"] for p in listed] == ["mine"]

    def test_a_recent_commit_lists_it(self, tmp_path):
        r = self._repo(tmp_path, "fresh", 2)
        listed, _ = rs.select_projects([{"name": "fresh", "path": str(r)}], days=30,
                                       now=time.time(), home=tmp_path, e2e_root=None)
        assert [p["active_by"] for p in listed] == [["commit"]]

    def test_a_hidden_project_is_left_out_and_counted(self, tmp_path):
        r = self._repo(tmp_path, "h", 2)
        listed, ex = rs.select_projects([{"name": "h", "path": str(r)}], days=30, now=time.time(),
                                        home=tmp_path, e2e_root=None, hidden=["h"])
        assert listed == [] and ex["hidden"] == 1

    def test_hiding_and_restoring_round_trips_through_local_config(self, tmp_path, monkeypatch):
        from set_orch import local_config
        store = {}
        monkeypatch.setattr(local_config, "get", lambda key, *a, **k: store.get(key))
        monkeypatch.setattr(local_config, "set_value", lambda key, value, *a, **k: store.__setitem__(key, value))
        assert rs.set_hidden("a", True) == ["a"]
        assert rs.set_hidden("b", True) == ["a", "b"]
        assert rs.set_hidden("a", False) == ["b"]
        assert rs.hidden_projects() == ["b"]

    def test_exclusions_are_counted_by_reason(self, tmp_path):
        e2e = tmp_path / "e2e"
        run = e2e / "run1"
        run.mkdir(parents=True)
        plain = tmp_path / "plain"
        plain.mkdir()
        projects = [
            {"name": "arch", "path": str(tmp_path), "archived": True},
            {"name": "run", "path": str(run)},
            {"name": "gone", "path": str(tmp_path / "nope")},
            {"name": "plain", "path": str(plain)},
        ]
        _, ex = rs.select_projects(projects, days=30, now=time.time(), home=tmp_path, e2e_root=e2e)
        assert (ex["archived"], ex["e2e_run"], ex["missing"], ex["not_git"]) == (1, 1, ["gone"], ["plain"])

    def test_the_window_comes_from_request_then_config_then_default(self, monkeypatch):
        from set_orch import local_config
        monkeypatch.setattr(local_config, "get", lambda key, *a, **k: "12")
        assert rs.window_days(5) == 5
        assert rs.window_days(None) == 12
        monkeypatch.setattr(local_config, "get", lambda key, *a, **k: None)
        assert rs.window_days(None) == rs.DEFAULT_DAYS
        assert rs.window_days(10_000) == rs.MAX_DAYS


# ─── the deploy hint ───────────────────────────────────────────────────────

class TestDeployHint:
    def _tree(self, tmp_path, files):
        root = tmp_path / "t"
        for rel, body in files.items():
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(body)
        root.mkdir(exist_ok=True)
        return root

    def test_an_automatic_production_job_on_this_branch_is_yes(self, tmp_path):
        root = self._tree(tmp_path, {".gitlab-ci.yml": (
            "deploy:\n  stage: deploy\n  script: [x]\n  rules:\n    - if: $CI_COMMIT_BRANCH == \"main\"\n"
            "  environment:\n    name: production\n")})
        h = rs.deploy_hint(root, "main")
        assert (h["value"], h["source"], h["environment"]) == ("yes", ".gitlab-ci.yml", "production")

    def test_the_same_job_on_another_branch_is_no(self, tmp_path):
        root = self._tree(tmp_path, {".gitlab-ci.yml": (
            "deploy:\n  stage: deploy\n  script: [x]\n  rules:\n    - if: $CI_COMMIT_BRANCH == \"main\"\n")})
        assert rs.deploy_hint(root, "dev")["value"] == "no"

    def test_a_manual_rule_is_not_a_deploy_on_push(self, tmp_path):
        root = self._tree(tmp_path, {".gitlab-ci.yml": (
            "deploy:\n  stage: deploy\n  script: [x]\n  rules:\n    - if: $CI_COMMIT_BRANCH == \"main\"\n"
            "      when: manual\n")})
        assert rs.deploy_hint(root, "main")["value"] != "yes"

    def test_a_job_level_manual_beside_rules_is_unknown_not_safe(self, tmp_path):
        root = self._tree(tmp_path, {".gitlab-ci.yml": (
            "deploy:\n  stage: deploy\n  when: manual\n  script: [x]\n  rules:\n"
            "    - if: $CI_COMMIT_BRANCH == \"main\"\n")})
        assert rs.deploy_hint(root, "main")["value"] == "unknown"

    def test_a_merge_request_only_rule_does_not_run_on_push(self, tmp_path):
        root = self._tree(tmp_path, {".gitlab-ci.yml": (
            "deploy:\n  stage: deploy\n  script: [x]\n  rules:\n"
            "    - if: $CI_PIPELINE_SOURCE == \"merge_request_event\"\n")})
        assert rs.deploy_hint(root, "main")["value"] == "no"

    def test_a_github_push_workflow_that_deploys_is_yes(self, tmp_path):
        root = self._tree(tmp_path, {".github/workflows/deploy.yml": (
            "name: Deploy site\non:\n  push:\n    branches: [main]\njobs:\n  build:\n    runs-on: x\n")})
        h = rs.deploy_hint(root, "main")
        assert (h["value"], h["source"]) == ("yes", ".github/workflows/deploy.yml")

    def test_a_github_dispatch_only_workflow_is_not_yes(self, tmp_path):
        root = self._tree(tmp_path, {".github/workflows/deploy.yml": (
            "name: Deploy\non:\n  workflow_dispatch: {}\njobs:\n  d:\n    runs-on: x\n")})
        assert rs.deploy_hint(root, "main")["value"] == "no"

    def test_a_linked_hosting_project_is_unknown_naming_the_file(self, tmp_path):
        root = self._tree(tmp_path, {"vercel.json": "{}"})
        h = rs.deploy_hint(root, "main")
        assert (h["value"], h["source"]) == ("unknown", "vercel.json")

    def test_an_unparseable_ci_file_is_unknown(self, tmp_path):
        root = self._tree(tmp_path, {".gitlab-ci.yml": "deploy: [unclosed\n"})
        assert rs.deploy_hint(root, "main")["value"] == "unknown"

    def test_no_ci_and_no_hosting_is_no(self, tmp_path):
        root = self._tree(tmp_path, {"README.md": "x"})
        assert rs.deploy_hint(root, "main")["value"] == "no"


# ─── the whole answer and the fetch ────────────────────────────────────────

class TestCollectAndFetch:
    def test_problem_rows_sort_first_and_are_counted(self, pair, tmp_path):
        work, _ = pair
        clean = tmp_path / "clean"
        git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(clean))
        (work / "dirty.txt").write_text("d\n")
        a = rs.collect(30, hidden=[], projects=[{"name": "zz-clean", "path": str(clean)},
                                     {"name": "aa-dirty", "path": str(work)},
                                     {"name": "mm-dirty", "path": str(work)}],
                       home=tmp_path, e2e_root=None)
        assert [r["name"] for r in a["projects"]] == ["aa-dirty", "mm-dirty", "zz-clean"]
        assert a["problem_count"] == 2 and a["days"] == 30

    def test_a_slow_remote_does_not_hold_the_others(self, pair, tmp_path, monkeypatch):
        work, _ = pair
        real = rs._fetch_one

        def fake(name, path, timeout):
            if name == "slow":
                return {"name": name, "result": "timeout", "reason": "no answer within 30s"}
            return real(name, path, timeout)

        monkeypatch.setattr(rs, "_fetch_one", fake)
        out = rs.fetch(["slow", "ok"], projects=[{"name": "slow", "path": str(work)},
                                                  {"name": "ok", "path": str(work)}])
        by = {r["name"]: r["result"] for r in out["results"]}
        assert by == {"slow": "timeout", "ok": "ok"}

    def test_a_fetch_that_times_out_is_reported_timeout(self, tmp_path, monkeypatch):
        def slow(*a, **k):
            raise subprocess.TimeoutExpired(cmd="git", timeout=1)

        monkeypatch.setattr(rs.subprocess, "run", slow)
        assert rs._fetch_one("p", str(tmp_path), 1)["result"] == "timeout"
