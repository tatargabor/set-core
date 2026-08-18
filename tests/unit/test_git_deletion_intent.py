"""Git history as the deletion-intent signal on a first init.

The ledger can only answer "did the project delete this?" for files set-core itself
recorded — which is nothing at all on the first run. Every absent path therefore
reads as new, and a deploy recreates the files the project threw out on purpose.
Measured on a live consumer: 11 resurrected files, all of them deletions the project
had committed.

What is pinned here is the shape of the signal, not just its happy path:

  * a committed deletion suppresses the deploy, and is written down as a tombstone
    so the second run does not need git at all;
  * a file merely absent — never in history — still deploys, or a new project would
    never receive its template;
  * a deleted-then-restored file deploys, because it is on disk and the question is
    never asked;
  * no git, no repository, or the escape hatch → the signal reports "unknown" and
    behaviour falls back exactly to what it was before.

That last one is the safety property. A signal that failed closed would freeze new
projects out of receiving any template file at all.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch import git_intent  # noqa: E402
from set_orch.deploy_ledger import DeployLedger  # noqa: E402
from set_orch.profile_deploy import _deploy_single_template  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_git_cache():
    git_intent.clear_cache()
    yield
    git_intent.clear_cache()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def repo(tmp_path):
    """A git repository with `doomed.md` committed and then deleted."""
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")

    _write(root / "doomed.md", "stale and wrong\n")
    _write(root / "kept.md", "still here\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "initial")

    (root / "doomed.md").unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "remove a rule that had gone stale")
    return root


# ── the signal itself ──────────────────────────────────────────────────────

def test_committed_deletion_is_reported(repo):
    assert git_intent.deleted_paths(repo) == frozenset({"doomed.md"})


def test_file_that_was_never_deleted_is_not_reported(repo):
    assert "kept.md" not in git_intent.deleted_paths(repo)


def test_non_repository_reports_unknown_not_empty(tmp_path):
    """None and frozenset() must stay distinguishable.

    An empty set would claim "nothing was ever deleted here" — a positive claim the
    caller would act on. None says "no information", which is the truth.
    """
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    assert git_intent.deleted_paths(plain) is None


def test_escape_hatch_disables_the_signal(repo, monkeypatch):
    monkeypatch.setenv("SET_DEPLOY_IGNORE_GIT_HISTORY", "1")
    git_intent.clear_cache()
    assert git_intent.deleted_paths(repo) is None


def test_paths_are_relative_to_the_deploy_root_not_the_repo_root(tmp_path):
    """Deploying into a subdirectory of a bigger repo must still match.

    Git reports repo-relative paths; ledger keys are project-relative. Left
    unadjusted the comparison silently matches nothing, and a guard that never fires
    is worse than no guard because it reads as protection.
    """
    root = tmp_path / "monorepo"
    (root / "apps" / "web").mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _write(root / "apps" / "web" / "doomed.md", "x\n")
    _write(root / "other" / "keep.md", "y\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "initial")
    (root / "apps" / "web" / "doomed.md").unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "delete")

    found = git_intent.deleted_paths(root / "apps" / "web")

    assert found == frozenset({"doomed.md"}), "prefix was not stripped"


# ── the ledger's decision ──────────────────────────────────────────────────

def test_ledger_skips_and_tombstones_a_path_deleted_in_history(repo):
    ledger = DeployLedger.load(repo)

    should_deploy, reason = ledger.decide("doomed.md", repo / "doomed.md")

    assert should_deploy is False
    assert "git history" in reason
    assert ledger.is_tombstoned("doomed.md"), "the decision was not written down"


def test_ledger_still_deploys_a_genuinely_new_file(repo):
    ledger = DeployLedger.load(repo)

    should_deploy, reason = ledger.decide("brand-new.md", repo / "brand-new.md")

    assert should_deploy is True
    assert reason == "new"


def test_tombstone_survives_so_the_second_run_needs_no_git(repo):
    ledger = DeployLedger.load(repo)
    ledger.decide("doomed.md", repo / "doomed.md")
    ledger.save()

    reloaded = DeployLedger.load(repo)
    assert reloaded.is_tombstoned("doomed.md")


def test_history_is_scanned_once_per_ledger_not_once_per_file(repo, monkeypatch):
    calls = []
    real = git_intent.deleted_paths

    def counting(root):
        calls.append(root)
        return real(root)

    monkeypatch.setattr("set_orch.deploy_ledger.git_deleted_paths", counting)
    ledger = DeployLedger.load(repo)
    for name in ("a.md", "b.md", "c.md", "doomed.md"):
        ledger.decide(name, repo / name)

    assert len(calls) == 1


# ── end to end through the manifest engine ─────────────────────────────────

def _template(tmp_path: Path, entries: str, files: dict) -> Path:
    template = tmp_path / "template"
    template.mkdir()
    _write(template / "manifest.yaml", 'version: "test"\ncore:\n' + entries)
    for rel, text in files.items():
        _write(template / rel, text)
    return template


def test_deploy_does_not_resurrect_a_file_the_project_deleted(repo, tmp_path):
    template = _template(
        tmp_path,
        "  - path: doomed.md\n    replace: true\n",
        {"doomed.md": "the framework's version\n"},
    )

    msgs = _deploy_single_template(template, repo, force=True)

    assert not (repo / "doomed.md").exists(), "a deliberate deletion was undone"
    assert any("deleted in git history" in m for m in msgs)


def test_deploy_still_creates_a_file_absent_from_history(repo, tmp_path):
    template = _template(
        tmp_path,
        "  - path: fresh.md\n    replace: true\n",
        {"fresh.md": "new content\n"},
    )

    _deploy_single_template(template, repo, force=True)

    assert (repo / "fresh.md").read_text() == "new content\n"


def test_restored_file_is_not_treated_as_deleted(repo, tmp_path):
    """Deleted, then brought back by hand: it exists, so history never gets asked."""
    _write(repo / "doomed.md", "the project changed its mind\n")
    template = _template(
        tmp_path,
        "  - path: doomed.md\n    replace: true\n",
        {"doomed.md": "framework version\n"},
    )

    _deploy_single_template(template, repo, force=True)

    assert (repo / "doomed.md").read_text() == "framework version\n"


def test_dry_run_records_no_tombstone(repo, tmp_path):
    template = _template(
        tmp_path,
        "  - path: doomed.md\n    replace: true\n",
        {"doomed.md": "framework version\n"},
    )

    _deploy_single_template(template, repo, force=True, dry_run=True)

    assert not (repo / "set" / ".deploy-manifest.json").exists()
    assert not (repo / "doomed.md").exists()
