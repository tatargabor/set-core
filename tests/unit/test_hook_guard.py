"""A command run in a worktree must not be able to rewire the host repository's hooks.

The failure this guards against was measured on a real repository, ten days after it
happened, and only while looking for something else. A dependency install inside a
throwaway worktree ran a `prepare` script, the hook installer wrote dispatchers containing
an absolute path INTO that worktree, and when the worktree was removed the host checkout's
hooks pointed at nothing. Everything hanging off them stopped running.

Three properties are what make it worth a module rather than a comment, and each has a test
below:

- git never shows it (hook managers gitignore their own directory), so a clean tree proves
  nothing;
- it fails silent and open — a hook that cannot run does not error, and a gate that never
  ran looks exactly like a gate that passed;
- the cause is deleted by the time the effect is noticed.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.hook_guard import (  # noqa: E402
    HOOK_INSTALLER_OPT_OUTS,
    capture_hook_wiring,
    guard_host_hooks,
    hook_safe_env,
    hook_wiring_changes,
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "host"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


# ── prevention ────────────────────────────────────────────────────────────

def test_the_env_carries_the_installers_own_opt_out_switches():
    """Not a set-core invention — these are what the tools themselves honour."""
    env = hook_safe_env()

    assert env["HUSKY"] == "0"
    assert env["LEFTHOOK"] == "0"


def test_an_explicit_value_wins_because_an_operator_knows_more_than_this_module():
    env = hook_safe_env({"HUSKY": "1", "OTHER": "x"})

    assert env["HUSKY"] == "1"
    assert env["LEFTHOOK"] == "0"
    assert env["OTHER"] == "x"


# ── detection: the half that does not depend on knowing the tool ──────────

def test_a_rewritten_hook_is_reported(tmp_path):
    repo = _repo(tmp_path)
    hooks = repo / ".git" / "hooks"
    (hooks / "pre-push").write_text("#!/bin/sh\nexec real-gate\n")
    before = capture_hook_wiring(repo)

    # What an installer run from a worktree leaves behind: the same file name, now
    # pointing at a path that will not exist once the worktree is gone.
    (hooks / "pre-push").write_text("#!/bin/sh\nexec /tmp/throwaway-wt/bin/lefthook\n")

    assert hook_wiring_changes(before, capture_hook_wiring(repo)) == [
        "hook rewritten: pre-push"
    ]


def test_a_redirected_hooksPath_is_reported_even_with_identical_files(tmp_path):
    """Both halves can be rewritten independently; catching only one is catching neither."""
    repo = _repo(tmp_path)
    before = capture_hook_wiring(repo)

    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    subprocess.run(
        ["git", "config", "core.hooksPath", str(elsewhere)], cwd=repo, check=True,
    )

    findings = hook_wiring_changes(before, capture_hook_wiring(repo))

    assert any("core.hooksPath changed" in f for f in findings), findings


def test_an_added_hook_is_reported_because_that_is_how_an_installer_arrives(tmp_path):
    repo = _repo(tmp_path)
    before = capture_hook_wiring(repo)
    (repo / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexec installer\n")

    assert hook_wiring_changes(before, capture_hook_wiring(repo)) == [
        "hook added: pre-commit"
    ]


def test_a_removed_hook_is_reported(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".git" / "hooks" / "pre-push").write_text("#!/bin/sh\nexec gate\n")
    before = capture_hook_wiring(repo)
    (repo / ".git" / "hooks" / "pre-push").unlink()

    assert hook_wiring_changes(before, capture_hook_wiring(repo)) == [
        "hook removed: pre-push"
    ]


def test_the_shipped_git_samples_are_not_hook_wiring(tmp_path):
    """`git init` writes a dozen `.sample` files that are wired to nothing. Counting them
    would make every baseline noisy, and noise is how a real finding gets skipped."""
    repo = _repo(tmp_path)

    assert not any(k.endswith(".sample") for k in capture_hook_wiring(repo))


def test_an_unchanged_repository_produces_no_findings(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".git" / "hooks" / "pre-push").write_text("#!/bin/sh\nexec gate\n")
    before = capture_hook_wiring(repo)

    assert hook_wiring_changes(before, capture_hook_wiring(repo)) == []


def test_no_baseline_reports_nothing_rather_than_reporting_calm(tmp_path):
    """Absence of information must not read as absence of change — the same false-absence
    shape this area keeps producing. An empty baseline means 'cannot say'."""
    repo = _repo(tmp_path)
    (repo / ".git" / "hooks" / "pre-push").write_text("#!/bin/sh\nexec gate\n")

    assert hook_wiring_changes({}, capture_hook_wiring(repo)) == []


# ── the worktree path, end to end ─────────────────────────────────────────

def test_a_worktree_writes_through_to_the_host_and_the_guard_sees_it(tmp_path):
    """The property that makes this possible at all: a worktree has no hooks of its own.

    This test exists because the mechanism is easy to disbelieve — the damage is done from
    a directory that is not the repository, to a file that is not in it.
    """
    repo = _repo(tmp_path)
    (repo / "f.txt").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=repo, check=True,
    )
    wt = tmp_path / "throwaway-wt"
    subprocess.run(["git", "worktree", "add", "-q", str(wt), "-b", "wt"], cwd=repo, check=True)

    before = capture_hook_wiring(wt)

    # Stand in for `pnpm install` → prepare → `lefthook install`: a process whose cwd is
    # the worktree, writing a hook that names a path inside that worktree.
    subprocess.run(
        ["git", "config", "core.hooksPath", str(wt / ".husky" / "_")], cwd=wt, check=True,
    )

    findings = guard_host_hooks(wt, before, context="test install")

    assert findings, "a hooksPath pointing into a throwaway worktree must be reported"
    # And the host repository is what actually changed — not the worktree.
    host_now = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    assert host_now == str(wt / ".husky" / "_"), (
        "the worktree wrote through to the host's shared config — this is the mechanism"
    )


def test_the_guard_does_not_repair(tmp_path):
    """Restoring would mean writing into a repository nobody asked this process to modify,
    and a wrong restore is indistinguishable from the damage. Reporting is the fix: the
    failure's whole problem was that it was silent."""
    repo = _repo(tmp_path)
    before = capture_hook_wiring(repo)
    (repo / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexec installer\n")

    guard_host_hooks(repo, before, context="test")

    assert (repo / ".git" / "hooks" / "pre-commit").exists()
