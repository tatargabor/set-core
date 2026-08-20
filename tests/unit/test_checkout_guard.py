"""set-hook-checkout-guard — the guard that stops one session in a shared
checkout from committing, sweeping or stashing another session's work.

Every refusal test here was checked by disabling the guard and re-running: a
test that passes without the thing it guards proves nothing and looks like
proof forever.
"""

import json
import os
import pathlib
import subprocess
import sys

import pytest

HOOK = pathlib.Path(__file__).resolve().parents[2] / "bin" / "set-hook-checkout-guard"

ALLOW, REFUSE = 0, 2


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", ".")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    (r / "base.txt").write_text("base\n")
    git(r, "add", "base.txt")
    git(r, "commit", "-qm", "base")
    return r


@pytest.fixture
def state_dir(tmp_path):
    d = tmp_path / "state"
    d.mkdir()
    return d


class Session:
    """One agent session: it runs commands through the hook, both events."""

    def __init__(self, name, repo, state_dir):
        self.name, self.repo, self.state_dir = name, repo, state_dir

    def _call(self, cmd, event):
        payload = {"session_id": self.name, "cwd": str(self.repo),
                   "hook_event_name": event, "tool_input": {"command": cmd}}
        env = dict(os.environ, SET_CHECKOUT_GUARD_STATE_DIR=str(self.state_dir))
        proc = subprocess.run([sys.executable, str(HOOK), event],
                              input=json.dumps(payload), capture_output=True,
                              text=True, env=env)
        return proc.returncode, proc.stderr

    def check(self, cmd):
        """What the guard says about a command, without running it."""
        return self._call(cmd, "PreToolUse")

    def run(self, cmd):
        """Guard, then actually run the command, then the post pass — the real
        sequence a session goes through."""
        rc, err = self._call(cmd, "PreToolUse")
        if rc != ALLOW:
            return rc, err
        subprocess.run(cmd, cwd=self.repo, shell=True, capture_output=True, text=True)
        return self._call(cmd, "PostToolUse")


@pytest.fixture
def alice(repo, state_dir):
    return Session("alice", repo, state_dir)


@pytest.fixture
def bob(repo, state_dir):
    return Session("bob", repo, state_dir)


# --- a commit may not carry another session's staged work ---------------------

def test_a_pathspec_less_commit_over_a_foreign_staged_path_is_refused(repo, alice, bob):
    (repo / "bob.txt").write_text("bob\n")
    bob.run("git add bob.txt")
    (repo / "alice.txt").write_text("alice\n")
    alice.run("git add alice.txt")

    rc, err = alice.check("git commit -m x")
    assert rc == REFUSE
    assert "bob.txt" in err, err
    assert "git commit --" in err
    assert "alice.txt" not in err.split("Staged, but not staged by this session:")[1] \
        .split("\n\n")[0]


def test_a_sessions_own_work_commits_without_interference(repo, alice):
    (repo / "alice.txt").write_text("alice\n")
    alice.run("git add alice.txt")
    rc, err = alice.check("git commit -m x")
    assert rc == ALLOW
    assert err == ""


def test_a_commit_that_names_its_paths_is_allowed_regardless(repo, alice, bob):
    (repo / "bob.txt").write_text("bob\n")
    bob.run("git add bob.txt")
    (repo / "alice.txt").write_text("alice\n")
    alice.run("git add alice.txt")
    assert alice.check("git commit -m x -- alice.txt")[0] == ALLOW


def test_amending_is_the_same_act(repo, alice, bob):
    (repo / "bob.txt").write_text("bob\n")
    bob.run("git add bob.txt")
    assert alice.check("git commit --amend -m x")[0] == REFUSE


# --- a staging command may not sweep what it was not given --------------------

@pytest.mark.parametrize("cmd", [
    "git add -A",
    "git add --all",
    "git add .",
    "git add -u",
    "git add -Av",
])
def test_a_sweeping_add_is_refused(alice, cmd):
    rc, err = alice.check(cmd)
    assert rc == REFUSE, cmd
    assert "git add <your paths>" in err


@pytest.mark.parametrize("cmd", [
    "git add alice.txt",
    "git add dir/ other.txt",
    "git add -u lib/",
])
def test_an_explicit_add_is_allowed(alice, cmd):
    assert alice.check(cmd)[0] == ALLOW, cmd


@pytest.mark.parametrize("cmd", ["git commit -a -m x", "git commit -am x",
                                 "git commit --all -m x"])
def test_staging_everything_tracked_is_the_same_sweep(alice, cmd):
    rc, err = alice.check(cmd)
    assert rc == REFUSE, cmd
    assert "every tracked modification" in err


# --- ownership is measured from the index, not parsed from the command --------

@pytest.mark.parametrize("stage_cmd", [
    "git add alice.txt",
    "git add alice*.txt",
    "F=alice.txt; git add $F",
    "printf 'alice.txt' | xargs git add",
])
def test_a_path_is_attributed_however_the_command_happened_to_name_it(
        repo, state_dir, stage_cmd):
    """The point of measuring instead of parsing: none of these name the path in
    a form an argument parser could resolve, and all four must attribute it."""
    alice = Session("alice-" + str(abs(hash(stage_cmd))), repo, state_dir)
    (repo / "alice.txt").write_text("alice\n")
    alice.run(stage_cmd)
    assert alice.check("git commit -m x") == (ALLOW, ""), stage_cmd


def test_a_path_that_appeared_outside_this_sessions_commands_is_foreign(repo, alice):
    """Staged by a hand at a terminal — no session ran it through the hook."""
    (repo / "stranger.txt").write_text("s\n")
    git(repo, "add", "stranger.txt")
    rc, err = alice.check("git commit -m x")
    assert rc == REFUSE
    assert "stranger.txt" in err


def test_a_session_that_staged_nothing_does_not_own_a_populated_index(repo, alice):
    (repo / "x.txt").write_text("x\n")
    git(repo, "add", "x.txt")
    assert alice.check("git commit -m x")[0] == REFUSE


def test_a_path_the_session_unstaged_stops_being_its_own(repo, alice, bob):
    (repo / "shared.txt").write_text("v1\n")
    alice.run("git add shared.txt")
    alice.run("git restore --staged shared.txt")
    bob.run("git add shared.txt")
    rc, err = alice.check("git commit -m x")
    assert rc == REFUSE, "alice's claim outlived the fact"
    assert "shared.txt" in err


def test_staging_and_committing_in_one_command_is_refused_with_the_composing_remedy(
        repo, alice):
    (repo / "alice.txt").write_text("alice\n")
    rc, err = alice.check("git add alice.txt && git commit -m x")
    assert rc == REFUSE
    assert "git add <your paths> && git commit -- <your paths>" in err


# --- the guard refuses, and changes nothing itself ----------------------------

def test_a_refusal_leaves_everything_where_it_was(repo, alice, bob):
    (repo / "bob.txt").write_text("bob\n")
    bob.run("git add bob.txt")
    before_index = subprocess.run(["git", "diff", "--cached", "--name-only"],
                                  cwd=repo, capture_output=True, text=True).stdout
    before_status = subprocess.run(["git", "status", "--porcelain"],
                                   cwd=repo, capture_output=True, text=True).stdout
    before_stash = subprocess.run(["git", "stash", "list"],
                                  cwd=repo, capture_output=True, text=True).stdout

    assert alice.check("git commit -m x")[0] == REFUSE

    assert subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=repo,
                          capture_output=True, text=True).stdout == before_index
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                          capture_output=True, text=True).stdout == before_status
    assert subprocess.run(["git", "stash", "list"], cwd=repo,
                          capture_output=True, text=True).stdout == before_stash


# --- the guard is silent where the hazard does not exist ----------------------

def test_a_dedicated_worktree_is_not_policed(repo, tmp_path, state_dir):
    """Each worktree has its own index, so an agent alone in one owns all of it."""
    (repo / "main.txt").write_text("m\n")
    git(repo, "add", "main.txt")
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "side")

    carol = Session("carol", wt, state_dir)
    (wt / "carol.txt").write_text("c\n")
    carol.run("git add carol.txt")
    assert carol.check("git commit -m x") == (ALLOW, ""), \
        "the main tree's staged path must not reach the worktree's guard"


def test_a_command_outside_a_repository_passes_through(tmp_path, state_dir):
    plain = tmp_path / "plain"
    plain.mkdir()
    s = Session("dave", plain, state_dir)
    assert s.check("git commit -m x") == (ALLOW, "")


@pytest.mark.parametrize("cmd", [
    "ls -la",
    "python -m pytest",
    "echo 'git commit'",
])
def test_a_non_git_command_is_not_inspected(alice, cmd):
    assert alice.check(cmd)[0] == ALLOW, cmd


def test_a_heredoc_that_merely_writes_about_committing_is_not_matched(alice):
    """Writing this file's own tests must not trip the guard — the measurement
    sitting inside the corpus it measures."""
    cmd = "cat > f.py <<'EOF'\ngit commit -a -m x\ngit add -A\nEOF"
    assert alice.check(cmd)[0] == ALLOW


@pytest.mark.parametrize("cmd", [
    "echo git add -A",
    "echo 'git commit -a -m x'",
    "grep -r 'git add -A' .",
])
def test_the_word_git_inside_another_command_is_not_a_git_invocation(alice, cmd):
    """The pre-filter is loose on purpose so `xargs git add` is seen; this is the
    other direction of that looseness, and it must not fire."""
    assert alice.check(cmd)[0] == ALLOW, cmd


def test_git_run_through_a_wrapper_is_still_a_git_invocation(alice):
    assert alice.check("xargs git add -A")[0] == REFUSE
    assert alice.check("git -C /tmp add -A")[0] == REFUSE


def test_the_measured_cure_end_to_end(repo, alice, bob):
    """The whole incident and its remedy, in one test.

    Bob stages his own path; Alice stages hers; Alice's pathspec-less commit is
    refused; Alice commits with `--` and Bob's staged entry is still there,
    untouched, and absent from the commit.
    """
    (repo / "bob.txt").write_text("bob\n")
    bob.run("git add bob.txt")
    (repo / "alice.txt").write_text("alice\n")
    alice.run("git add alice.txt")

    assert alice.check("git commit -m x")[0] == REFUSE

    rc, _ = alice.run("git commit -m x -- alice.txt")
    assert rc == ALLOW

    committed = subprocess.run(["git", "show", "--name-only", "--format=", "HEAD"],
                               cwd=repo, capture_output=True, text=True).stdout.split()
    assert committed == ["alice.txt"], committed
    still_staged = subprocess.run(["git", "diff", "--cached", "--name-only"],
                                  cwd=repo, capture_output=True, text=True).stdout.split()
    assert still_staged == ["bob.txt"], still_staged


# --- a stash that names no paths is refused while the checkout holds work ------

def test_a_bare_stash_over_uncommitted_work_is_refused(repo, alice):
    (repo / "someone.txt").write_text("work\n")
    rc, err = alice.check("git stash")
    assert rc == REFUSE
    assert "someone.txt" in err


def test_the_refusal_explains_why_this_one_is_worse_than_a_commit(repo, alice):
    (repo / "someone.txt").write_text("work\n")
    _, err = alice.check("git stash")
    assert "reads CLEAN" in err
    assert "no reason to look in" in err


def test_a_bare_stash_is_refused_even_when_the_work_looks_like_the_sessions_own(
        repo, alice):
    """The refusal does not depend on attribution, because a working-tree
    modification cannot be attributed by this mechanism at all."""
    (repo / "alice.txt").write_text("alice\n")
    alice.run("git add alice.txt")
    assert alice.check("git stash")[0] == REFUSE


@pytest.mark.parametrize("cmd", [
    "git stash push -- alice.txt",
    "git stash push -m note -- alice.txt",
    "git stash -- alice.txt",
])
def test_stashing_named_paths_is_allowed(repo, alice, cmd):
    (repo / "alice.txt").write_text("alice\n")
    assert alice.check(cmd)[0] == ALLOW, cmd


@pytest.mark.parametrize("cmd", [
    "git stash list",
    "git stash show",
    "git stash pop",
    "git stash drop",
])
def test_reading_the_stash_is_not_taking_anything(repo, alice, cmd):
    (repo / "someone.txt").write_text("work\n")
    assert alice.check(cmd)[0] == ALLOW, cmd


def test_a_clean_checkout_has_nothing_to_take(alice):
    assert alice.check("git stash") == (ALLOW, "")


def test_a_stash_message_is_not_mistaken_for_a_pathspec(repo, alice):
    """`git stash -m 'note'` still sweeps everything; the message is not a path."""
    (repo / "someone.txt").write_text("work\n")
    assert alice.check("git stash -m 'saving my work'")[0] == REFUSE


@pytest.mark.parametrize("cmd", ["git stash push", "git stash save", "git stash push -m note"])
def test_a_bare_push_or_save_sweeps_just_as_much_as_a_bare_stash(repo, alice, cmd):
    """The subcommand is not a pathspec. Missing this reads `push` as a named path
    and allows the sweep — the permissive direction, found by mutation."""
    (repo / "someone.txt").write_text("work\n")
    assert alice.check(cmd)[0] == REFUSE, cmd
