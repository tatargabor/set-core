"""Where the fleet screen may start an agent — the list, and what the guard refuses.

Change `fleet-start-agent-in-worktree`. Two readers must agree: the form offers
locations, the endpoint accepts them. These tests build a REAL git repository
with a real worktree in `tmp_path` rather than stubbing the porcelain, because
the thing under test is a rule about git's own answer — a stub would measure the
fixture.

The refusal cases assert that the owner service was never asked. A guard that
refuses *after* starting a process is not a guard, and "returned 400" alone
cannot tell the two apart.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest
from fastapi import HTTPException

from set_orch.api import fleet as fleet_api
from set_orch.api.fleet import StartAgentBody


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A repository with one commit, plus a worktree on a change/ branch."""
    root = tmp_path / "project"
    root.mkdir()
    _git("init", "-q", "-b", "main", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "t", cwd=root)
    (root / "README.md").write_text("x\n")
    _git("add", "README.md", cwd=root)
    _git("commit", "-qm", "init", cwd=root)

    wt = tmp_path / "project-add-auth"
    _git("worktree", "add", "-q", "-b", "change/add-auth", str(wt), cwd=root)

    (root / "lib").mkdir()
    return {
        "root": os.path.realpath(str(root)),
        "worktree": os.path.realpath(str(wt)),
        "subdir": os.path.realpath(str(root / "lib")),
    }


class _Owner:
    """Records whether a start was ever asked for."""

    def __init__(self):
        self.started = []

    def start(self, **kwargs):
        self.started.append(kwargs)
        return {"label": kwargs["label"], "pid": 4242, "cwd": kwargs["cwd"]}


@pytest.fixture
def owner(monkeypatch):
    held = _Owner()
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: held)
    return held


# --------------------------------------------------------------------------- #
# the verdict
# --------------------------------------------------------------------------- #

def test_a_known_project_root_is_accepted_as_a_root(repo, monkeypatch):
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {repo["root"]})
    assert fleet_api._start_location_verdict(repo["root"]) == (True, "root")


def test_a_worktree_of_a_known_project_is_accepted_as_a_worktree(repo, monkeypatch):
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {repo["root"]})
    assert fleet_api._start_location_verdict(repo["worktree"]) == (True, "worktree")


def test_a_subdirectory_of_a_known_project_is_refused(repo, monkeypatch):
    """The case a prefix test would have let in — and `lib/` is inside the repo."""
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {repo["root"]})
    allowed, why = fleet_api._start_location_verdict(repo["subdir"])
    assert (allowed, why) == (False, "unknown")


def test_a_worktree_of_an_UNKNOWN_project_is_refused(repo, monkeypatch):
    """Being a worktree is not enough — it must belong to a project on screen."""
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: set())
    assert fleet_api._start_location_verdict(repo["worktree"]) == (False, "unknown")


def test_a_directory_outside_every_repository_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: set())
    loose = tmp_path / "loose"
    loose.mkdir()
    assert fleet_api._start_location_verdict(str(loose)) == (False, "unknown")


def test_a_prunable_worktree_is_refused_with_prunable_as_the_reason(repo, monkeypatch):
    """The guard's prunable branch, reached with the location list stubbed — and
    the stub is the honest way to test it, for a reason worth writing down.

    Measured while writing this: on every path a real prunable worktree can take,
    the guard refuses it *before* the prunable check. Its directory is gone, so
    `isdir` refuses first; or the directory came back empty, so git no longer
    finds the repository from it and the answer is `unknown`; or the admin
    `gitdir` file was repointed, in which case git reports the entry under the
    NEW path and the submitted one is not in the list at all.

    So this branch is defence in depth, not the common path — and saying so is
    the point. Deleting it because "nothing reaches it" would rest on today's git
    behaviour, and the list endpoint DOES produce real prunable entries (see
    `test_a_prunable_entry_is_listed_and_marked_rather_than_dropped`), which the
    form filters. A guard that trusts the form to have filtered is not a guard.
    """
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {repo["root"]})
    monkeypatch.setattr(
        fleet_api, "list_worktree_locations",
        lambda root: [
            {"path": repo["root"], "branch": "main", "is_main": True, "prunable": False},
            {"path": repo["worktree"], "branch": "change/add-auth",
             "is_main": False, "prunable": True},
        ],
    )
    assert fleet_api._start_location_verdict(repo["worktree"]) == (False, "prunable")


# --------------------------------------------------------------------------- #
# the endpoint
# --------------------------------------------------------------------------- #

def test_starting_in_a_worktree_asks_the_owner_for_that_directory(repo, owner, monkeypatch):
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {repo["root"]})
    agent = fleet_api.fleet_start_agent(
        StartAgentBody(label="wt-agent", cwd=repo["worktree"])
    )
    assert owner.started and owner.started[0]["cwd"] == repo["worktree"]
    assert agent["cwd"] == repo["worktree"]


def test_starting_in_the_root_still_works(repo, owner, monkeypatch):
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {repo["root"]})
    fleet_api.fleet_start_agent(StartAgentBody(label="root-agent", cwd=repo["root"]))
    assert owner.started[0]["cwd"] == repo["root"]


def test_a_refused_subdirectory_never_reaches_the_owner(repo, owner, monkeypatch):
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {repo["root"]})
    with pytest.raises(HTTPException) as exc:
        fleet_api.fleet_start_agent(StartAgentBody(label="nope", cwd=repo["subdir"]))
    assert exc.value.status_code == 400
    assert repo["subdir"] in str(exc.value.detail)
    assert owner.started == [], "the guard refused only after starting an agent"


def test_a_refused_outside_directory_never_reaches_the_owner(tmp_path, owner, monkeypatch):
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: set())
    loose = tmp_path / "loose"
    loose.mkdir()
    with pytest.raises(HTTPException) as exc:
        fleet_api.fleet_start_agent(StartAgentBody(label="nope", cwd=str(loose)))
    assert exc.value.status_code == 400
    assert owner.started == []


def test_the_prunable_refusal_says_why_rather_than_naming_the_registry(repo, owner, monkeypatch):
    """A wrong reason sends the reader to register a project that is registered."""
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {repo["root"]})
    monkeypatch.setattr(
        fleet_api, "list_worktree_locations",
        lambda root: [{"path": repo["worktree"], "branch": "change/add-auth",
                       "is_main": False, "prunable": True}],
    )
    with pytest.raises(HTTPException) as exc:
        fleet_api.fleet_start_agent(StartAgentBody(label="nope", cwd=repo["worktree"]))
    assert exc.value.status_code == 400
    assert "prunable" in str(exc.value.detail)
    assert owner.started == []


# --------------------------------------------------------------------------- #
# the list
# --------------------------------------------------------------------------- #

def _listed(monkeypatch, repo, name="proj"):
    class _P:
        def __init__(self):
            self.name = name
            self.root = repo["root"]
    monkeypatch.setattr(fleet_api, "discover_agents", lambda **k: [])
    monkeypatch.setattr(fleet_api, "discover_projects", lambda *a, **k: [_P()])


def test_the_list_names_the_main_checkout_and_every_worktree(repo, monkeypatch):
    _listed(monkeypatch, repo)
    answer = fleet_api.fleet_project_worktrees("proj")
    paths = [loc["path"] for loc in answer["locations"]]
    assert os.path.realpath(paths[0]) == repo["root"]
    assert repo["worktree"] in [os.path.realpath(p) for p in paths]
    assert [loc["is_main"] for loc in answer["locations"]].count(True) == 1


def test_the_list_carries_the_branch_of_each_worktree(repo, monkeypatch):
    _listed(monkeypatch, repo)
    answer = fleet_api.fleet_project_worktrees("proj")
    branches = {loc["branch"] for loc in answer["locations"]}
    assert branches == {"main", "change/add-auth"}


def test_a_prunable_entry_is_listed_and_marked_rather_than_dropped(repo, monkeypatch):
    """A real prunable entry: the worktree directory is gone and came back empty.

    That is how the three prunable entries in this project's own repository came
    about — a temporary checkout removed by whatever created it.
    """
    _listed(monkeypatch, repo)
    shutil.rmtree(repo["worktree"])
    os.mkdir(repo["worktree"])
    answer = fleet_api.fleet_project_worktrees("proj")
    assert any(loc["prunable"] for loc in answer["locations"])
    # Present, not filtered — the caller decides what to do with it.
    assert len(answer["locations"]) == 2


def test_a_project_with_no_worktrees_lists_only_its_checkout(tmp_path, monkeypatch):
    root = tmp_path / "solo"
    root.mkdir()
    _git("init", "-q", "-b", "main", cwd=root)

    class _P:
        name = "solo"
        root_ = None
    p = _P()
    p.root = os.path.realpath(str(root))
    monkeypatch.setattr(fleet_api, "discover_agents", lambda **k: [])
    monkeypatch.setattr(fleet_api, "discover_projects", lambda *a, **k: [p])
    answer = fleet_api.fleet_project_worktrees("solo")
    assert len(answer["locations"]) == 1
    assert answer["locations"][0]["is_main"] is True


def test_an_unlisted_project_is_404_rather_than_resolved_from_the_filesystem(monkeypatch):
    monkeypatch.setattr(fleet_api, "discover_agents", lambda **k: [])
    monkeypatch.setattr(fleet_api, "discover_projects", lambda *a, **k: [])
    with pytest.raises(HTTPException) as exc:
        fleet_api.fleet_project_worktrees("nothing-like-this")
    assert exc.value.status_code == 404
    assert "nothing-like-this" in str(exc.value.detail)


def test_a_non_git_project_still_offers_its_root_rather_than_an_empty_list(tmp_path, monkeypatch):
    """An empty list would read as 'nowhere to start' — a false absence."""
    root = tmp_path / "plain"
    root.mkdir()

    class _P:
        name = "plain"
    p = _P()
    p.root = os.path.realpath(str(root))
    monkeypatch.setattr(fleet_api, "discover_agents", lambda **k: [])
    monkeypatch.setattr(fleet_api, "discover_projects", lambda *a, **k: [p])
    answer = fleet_api.fleet_project_worktrees("plain")
    assert answer["locations"] == [
        {"path": p.root, "branch": "", "is_main": True, "prunable": False}
    ]
