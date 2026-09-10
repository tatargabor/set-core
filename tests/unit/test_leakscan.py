"""Tests for bin/set-leakscan — the gate that refuses to publish what must not leave.

Every test here holds a shape that was WRONG at some point, not merely the
behaviour that is right. Two of them exist because the first version of the
scanner fired on them and a noisy gate is a gate that gets bypassed; one exists
because a scan that cannot see a category must say so instead of reporting zero.
"""

import getpass
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

SCANNER = Path(__file__).resolve().parents[2] / "bin" / "set-leakscan"
CONSUMER = "acme-invoicing"          # stands in for a private consumer slug


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git("init", "-q", cwd=r)
    git("config", "user.email", "t@example.com", cwd=r)
    git("config", "user.name", "t", cwd=r)
    return r


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A project registry holding one private consumer, outside any repository."""
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    reg = cfg / "projects.json"
    reg.write_text(json.dumps({
        "projects": {CONSUMER: {"path": f"/home/{getpass.getuser()}/code/{CONSUMER}"}}
    }))
    return reg


def run(repo, registry, *args, allow=None):
    env = dict(os.environ, HOME=str(registry.parent.parent))
    # the scanner resolves REGISTRY from HOME at import time, so point HOME at
    # a tree shaped like the real one
    cfgdir = registry.parent.parent / ".config" / "set-core"
    cfgdir.mkdir(parents=True, exist_ok=True)
    (cfgdir / "projects.json").write_text(registry.read_text())
    if allow is not None:
        (cfgdir / "leakscan-allow.txt").write_text(allow)
    return subprocess.run([sys.executable, str(SCANNER), *args],
                          cwd=repo, capture_output=True, text=True, env=env)


def commit(repo, name, body, msg="wip"):
    (repo / name).write_text(body)
    git("add", name, cwd=repo)
    git("commit", "-q", "-m", msg, cwd=repo)


class TestItFires:
    def test_a_consumer_name_in_content_is_a_finding(self, repo, registry):
        commit(repo, "notes.md", f"lesson from the {CONSUMER} project\n")
        r = run(repo, registry, "--tree")
        assert r.returncode == 1
        assert "consumer-name" in r.stderr

    def test_a_consumer_name_in_a_commit_message_is_a_finding(self, repo, registry):
        # A message is in no diff and in no tree, so a content-only scan is
        # structurally blind to it.
        commit(repo, "x.md", "clean\n", msg=f"fix: {CONSUMER} reported this")
        r = run(repo, registry, "--tree")
        assert r.returncode == 1
        assert "commit-message" in r.stderr

    def test_a_credential_is_a_finding(self, repo, registry):
        commit(repo, "c.md", "key: sk-ant-api03-" + "A" * 24 + "\n")
        r = run(repo, registry, "--tree")
        assert r.returncode == 1
        assert "secret" in r.stderr

    def test_a_file_tracked_despite_being_gitignored_is_a_finding(self, repo, registry):
        commit(repo, "secret.env", "TOKEN=x\n")
        commit(repo, ".gitignore", "*.env\n")
        r = run(repo, registry, "--tree")
        assert r.returncode == 1
        assert "ignored-but-tracked" in r.stderr


class TestItStaysQuietOnWhatIsNotALeak:
    def test_a_url_path_segment_is_not_a_filesystem_path(self, repo, registry):
        # The unanchored pattern read `https://www.atia.org/home/at-resources/`
        # as a home directory and fired on two ordinary documentation links.
        commit(repo, "links.md", "see https://www.atia.org/home/at-resources/ for more\n")
        r = run(repo, registry, "--tree")
        assert r.returncode == 0, r.stderr

    def test_an_anonymised_example_path_is_not_this_machines_layout(self, repo, registry):
        # A repository that FOLLOWS the confidentiality rule is full of these.
        # Flagging them is how a gate earns its way into `--no-verify`.
        commit(repo, "doc.md",
               "e.g. /home/someone/clients/acme/set/modules.yaml\n"
               "PATH=/home/linuxbrew/.linuxbrew/bin\n")
        r = run(repo, registry, "--tree")
        assert r.returncode == 0, r.stderr

    def test_this_machines_own_home_path_IS_a_finding(self, repo, registry):
        # The other half of the pair above: narrowing must not blind it.
        commit(repo, "doc.md", f"see /home/{getpass.getuser()}/code/x for the script\n")
        r = run(repo, registry, "--tree")
        assert r.returncode == 1
        assert "home-path" in r.stderr

    def test_an_allowlisted_slug_is_suppressed(self, repo, registry):
        commit(repo, "notes.md", f"the {CONSUMER} project\n")
        r = run(repo, registry, "--tree", allow=f"{CONSUMER}\n")
        assert r.returncode == 0, r.stderr


class TestAGapIsNotAZero:
    def test_a_missing_registry_is_announced_not_folded_into_a_clean_result(
            self, repo, tmp_path):
        # Without this, an unreadable registry produces an empty pattern list,
        # every name check silently passes, and the gate reports a clean push
        # for a repository it never examined for names.
        home = tmp_path / "emptyhome"
        (home / ".config" / "set-core").mkdir(parents=True)
        commit(repo, "notes.md", f"the {CONSUMER} project\n")
        r = subprocess.run([sys.executable, str(SCANNER), "--tree"],
                           cwd=repo, capture_output=True, text=True,
                           env=dict(os.environ, HOME=str(home)))
        assert "SKIPPED" in r.stderr, r.stderr


class TestTheScannerDoesNotFindItself:
    def test_its_own_secret_patterns_are_not_findings(self, repo, registry):
        # The measurement is inside the corpus it measures: a file listing
        # credential regexes matches them. Both the scanner and the rule file
        # that documents the same patterns are excluded by path.
        (repo / "bin").mkdir()
        (repo / "bin" / "set-leakscan").write_text(SCANNER.read_text())
        git("add", "-A", cwd=repo)
        git("commit", "-q", "-m", "vendor the scanner", cwd=repo)
        r = run(repo, registry, "--tree")
        assert "secret" not in r.stderr, r.stderr


HOOK = Path(__file__).resolve().parents[2] / "bin" / "set-hook-leakscan"


def _hook(session_dir, command, home):
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash", "cwd": str(session_dir),
                          "tool_input": {"command": command}}),
        capture_output=True, text=True, cwd=str(session_dir),
        env=dict(os.environ, HOME=str(home)),
    )


@pytest.fixture
def two_repos(tmp_path, registry):
    """A repository that leaks and one that does not, plus a prepared HOME."""
    home = registry.parent.parent
    cfg = home / ".config" / "set-core"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "projects.json").write_text(registry.read_text())

    dirty, clean = tmp_path / "dirty", tmp_path / "clean"
    for r, body in ((dirty, f"the {CONSUMER} project\n"), (clean, "nothing here\n")):
        r.mkdir()
        git("init", "-q", cwd=r)
        git("config", "user.email", "t@example.com", cwd=r)
        git("config", "user.name", "t", cwd=r)
        (r / "notes.md").write_text(body)
        git("add", "-A", cwd=r)
        git("commit", "-q", "-m", "init", cwd=r)
    return dirty, clean, home


class TestTheHookScansTheRepositoryTheCommandTargets:
    """The hook runs in the SESSION's directory, not the command's.

    Measured on the first live push: it listed findings from an unrelated
    repository and refused a clean one. The fail direction runs both ways — it
    blocks a correct push, and it would PASS a leaking one whenever the session
    directory happens to be clean and the target is not.
    """

    def test_a_leading_cd_decides_which_repository_is_scanned(self, two_repos):
        dirty, clean, home = two_repos
        # Session in the CLEAN repo, push from the DIRTY one. Scanning the
        # session directory would wave this through.
        r = _hook(clean, f"cd {dirty}\ngit " + "push --force origin main", home)
        assert r.returncode == 2, f"the leaking target was not scanned: {r.stderr}"
        assert CONSUMER in r.stderr

    def test_and_it_does_not_falsely_block_a_clean_target(self, two_repos):
        dirty, clean, home = two_repos
        r = _hook(dirty, f"cd {clean} && git " + "push origin main", home)
        assert r.returncode == 0, f"a clean push was refused: {r.stderr}"

    def test_without_a_cd_the_session_directory_is_the_target(self, two_repos):
        dirty, _clean, home = two_repos
        r = _hook(dirty, "git " + "push origin main", home)
        assert r.returncode == 2, r.stderr


class TestTheHookIsNotTriggeredByTextThatMerelyMentionsPushing:
    """A heredoc body that WRITES about pushing is not a push.

    Measured while writing this very file: `cat > test.py <<'EOF' … EOF` whose
    body contained the verb was refused by the hook, so the test that hardens
    the gate could not be written through it. That is the measurement sitting
    inside the corpus it measures.
    """

    def test_a_heredoc_body_containing_the_verb_is_not_a_publication(self, two_repos):
        dirty, _clean, home = two_repos
        cmd = "cat > t.py <<'XEOF'\nrun('git " + "push origin main')\nXEOF"
        r = _hook(dirty, cmd, home)
        assert r.returncode == 0, r.stderr

    def test_but_a_real_command_after_the_heredoc_still_counts(self, two_repos):
        dirty, _clean, home = two_repos
        cmd = "cat > t.py <<'XEOF'\nx = 1\nXEOF\ngit " + "push origin main"
        r = _hook(dirty, cmd, home)
        assert r.returncode == 2, r.stderr

    def test_a_local_commit_is_not_a_publication(self, two_repos):
        dirty, _clean, home = two_repos
        r = _hook(dirty, "git commit -m 'wip'", home)
        assert r.returncode == 0, r.stderr

    def test_a_local_tag_is_not_a_publication_either(self, two_repos):
        """B-70. A tag writes a ref into `.git` and reaches nobody.

        The direction is what makes this worth a test rather than a tidy-up: the
        gate blocked `git tag <name> HEAD && git filter-branch --msg-filter …`,
        which is the REPAIR for the findings it had just reported — and
        `release-safety.md` prescribes exactly that backup tag before a history
        rewrite. A guard standing in front of its own rule book's fix is how a
        guard earns its way into `--no-verify`.

        Scanned in the DIRTY repository deliberately: a clean one would pass for
        the wrong reason, and the assertion would hold with `tag` still in the
        pattern.
        """
        dirty, _clean, home = two_repos
        r = _hook(dirty, "git " + "tag leakscan-backup-x HEAD", home)
        assert r.returncode == 0, f"a local tag was refused: {r.stderr}"

    def test_but_pushing_tags_to_a_remote_still_is(self, two_repos):
        """The positive control, and it is not optional.

        Narrowing a safety gate is only allowed to remove a false block; if it
        also opened a hole, this is where it shows. Every route a tag has to a
        remote goes through `push`.
        """
        dirty, _clean, home = two_repos
        for cmd in ("git " + "push --tags",
                    "git " + "push origin v1.2.3",
                    "git " + "push origin refs/tags/v1.2.3"):
            r = _hook(dirty, cmd, home)
            assert r.returncode == 2, f"{cmd!r} was not scanned: {r.stderr}"


class TestARepositoryMayNameItself:
    """The gate ran inside one of the private projects and reported 893 findings
    of its own name. That is not a leak in any direction, and it would make the
    tool unusable exactly where somebody most needs to push."""

    def test_the_repositorys_own_directory_name_is_not_a_finding(
            self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        cfg = home / ".config" / "set-core"
        cfg.mkdir(parents=True)
        (cfg / "projects.json").write_text(json.dumps(
            {"projects": {"acme-shop": {"path": "/somewhere/acme-shop"}}}))

        repo = tmp_path / "acme-shop"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        git("config", "user.email", "t@example.com", cwd=repo)
        git("config", "user.name", "t", cwd=repo)
        (repo / "README.md").write_text("acme-shop is this project\n")
        git("add", "-A", cwd=repo)
        git("commit", "-q", "-m", "init", cwd=repo)

        r = subprocess.run([sys.executable, str(SCANNER), "--tree"],
                           cwd=repo, capture_output=True, text=True,
                           env=dict(os.environ, HOME=str(home)))
        assert r.returncode == 0, r.stderr

    def test_but_a_DIFFERENT_projects_name_still_is(self, tmp_path):
        # The other half: the exclusion must not blind the check.
        home = tmp_path / "home"
        cfg = home / ".config" / "set-core"
        cfg.mkdir(parents=True)
        (cfg / "projects.json").write_text(json.dumps(
            {"projects": {"acme-shop": {"path": "/somewhere/acme-shop"},
                          "other-client": {"path": "/somewhere/other-client"}}}))

        repo = tmp_path / "acme-shop"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        git("config", "user.email", "t@example.com", cwd=repo)
        git("config", "user.name", "t", cwd=repo)
        (repo / "README.md").write_text("we borrowed this from other-client\n")
        git("add", "-A", cwd=repo)
        git("commit", "-q", "-m", "init", cwd=repo)

        r = subprocess.run([sys.executable, str(SCANNER), "--tree"],
                           cwd=repo, capture_output=True, text=True,
                           env=dict(os.environ, HOME=str(home)))
        assert r.returncode == 1
        assert "other-client" in r.stderr


# ─── the env-marker category and the commit gate ─────────────────────
# Identity for these fixtures is FICTIONAL on purpose, and derived from the
# fixture repository's own git config rather than from this machine: a test
# file carrying the real user's name is exactly what the gate must refuse at
# commit time — the measurement sitting inside the corpus it measures, again.

@pytest.fixture
def identity_repo(tmp_path):
    """A repo whose git identity is a fictional name with real token shape."""
    r = tmp_path / "proj"
    r.mkdir()
    git("init", "-q", cwd=r)
    git("config", "user.email", "ada.lovelace@example.com", cwd=r)
    git("config", "user.name", "Ada Lovelace", cwd=r)
    return r


def stage(repo, name, body):
    (repo / name).write_text(body)
    git("add", name, cwd=repo)


def run_scan(repo, *args, allow=None):
    """Run the scanner with a redirected HOME and an EMPTY registry, so the
    env-marker assertions answer only for the env-marker machinery."""
    home = repo.parent / "home"
    cfg = home / ".config" / "set-core"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "projects.json").write_text(json.dumps({"projects": {}}))
    if allow is not None:
        (cfg / "leakscan-allow.txt").write_text(allow)
    return subprocess.run([sys.executable, str(SCANNER), *args],
                          cwd=repo, capture_output=True, text=True,
                          env=dict(os.environ, HOME=str(home)))


class TestEnvMarkersResolveAtRunTime:
    def test_a_name_with_diacritics_is_still_found(self, tmp_path):
        repo = tmp_path / "proj"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        git("config", "user.email", "iron@test.io", cwd=repo)
        git("config", "user.name", "Írón Teszt", cwd=repo)
        stage(repo, "a.md", "plain text about Írón Teszt\n")
        r = run_scan(repo, "--staged")
        assert r.returncode == 1, r.stderr
        assert "env-marker" in r.stderr

    def test_the_account_handle_in_a_url_is_not_the_prose_name(
            self, identity_repo):
        # The word boundary is the rule, and it is stated, not accidental: the
        # tree legitimately carries the author's PUBLIC handle inside clone
        # URLs — one unbroken word — while prose uses of the name must fire.
        stage(identity_repo, "a.md",
              "clone https://github.com/adalovelace/set-core.git\n")
        r = run_scan(identity_repo, "--staged")
        assert r.returncode == 0, r.stderr

    def test_but_the_prose_name_still_fires(self, identity_repo):
        stage(identity_repo, "a.md", "as Ada Lovelace noted\n")
        r = run_scan(identity_repo, "--staged")
        assert r.returncode == 1, r.stderr
        assert "env-marker" in r.stderr

    def test_a_stoplisted_identity_token_does_not_fire(self, tmp_path):
        repo = tmp_path / "proj"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        git("config", "user.email", "test.admin@example.com", cwd=repo)
        git("config", "user.name", "Test Admin", cwd=repo)
        stage(repo, "a.md", "Test Admin wrote the test docs\n")
        r = run_scan(repo, "--staged")
        assert r.returncode == 0, r.stderr

    def test_the_username_and_hostname_fire(self, tmp_path):
        # The real login name and hostname are env-specific whatever the git
        # config says — resolved from the machine, not the repository.
        repo = tmp_path / "proj"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        git("config", "user.email", "n@example.com", cwd=repo)
        git("config", "user.name", "n", cwd=repo)
        candidates = [getpass.getuser(),
                      socket.gethostname(), socket.gethostname().split(".")[0]]
        marker = next((c for c in candidates
                       if len(c) >= 2 and c.lower() not in
                       {"user", "admin", "test", "main", "local", "home",
                        "host", "dev", "git", "root", "info", "mail",
                        "gmail", "example", "com", "org", "net"}), None)
        assert marker, "this machine offers no usable identity to test with"
        stage(repo, "a.md", f"configured for {marker} on this box\n")
        r = run_scan(repo, "--staged")
        assert r.returncode == 1, r.stderr
        assert "env-marker" in r.stderr

    def test_the_repositorys_own_tokens_are_suppressed(self, tmp_path):
        repo = tmp_path / "lovelace"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        git("config", "user.email", "ada@lovelace.io", cwd=repo)
        git("config", "user.name", "Ada", cwd=repo)
        stage(repo, "a.md", "lovelace is this project\n")
        r = run_scan(repo, "--staged")
        assert r.returncode == 0, r.stderr


class TestDeliberateExceptionsAreRecorded:
    def test_a_literal_allow_entry_suppresses_its_line_only(
            self, identity_repo):
        stage(identity_repo, "a.md", "noted by Ada Lovelace\na clean line\n")
        r = run_scan(identity_repo, "--staged", allow="literal:ada lovelace\n")
        assert r.returncode == 0, r.stderr

    def test_the_exception_is_line_local_not_blanket(self, identity_repo):
        stage(identity_repo, "a.md", "nothing to see\nnoted by Ada Lovelace\n")
        r = run_scan(identity_repo, "--staged", allow="literal:a clean line\n")
        assert r.returncode == 1, "an unrelated literal opened the gate"
        assert "env-marker" in r.stderr


class TestAGapInTheEnvironmentIsAnnounced:
    def test_unset_git_identity_is_a_loud_partial_blindness_not_a_clean(
            self, tmp_path):
        repo = tmp_path / "proj"
        repo.mkdir()
        git("init", "-q", cwd=repo)          # no user.email / user.name set
        stage(repo, "a.md", "key: sk-ant-api03-" + "A" * 24 + "\n")
        r = run_scan(repo, "--staged")
        assert r.returncode == 1
        assert "partially blind" in r.stderr, r.stderr
        assert "secret" in r.stderr, "the checks that COULD run went silent"


class TestTheCommitGateMeasuresAddedLines:
    def test_a_new_file_carrying_the_hostname_is_refused(self, identity_repo):
        host = socket.gethostname().split(".")[0]
        stage(identity_repo, "a.md", f"server {host} internal\n")
        r = run_scan(identity_repo, "--staged")
        assert r.returncode == 1, r.stderr

    def test_preexisting_contamination_beside_a_clean_edit_does_not_block(
            self, identity_repo):
        commit(identity_repo, "a.md", "as Ada Lovelace noted long ago\n",
               msg="seed")
        stage(identity_repo, "a.md",
              "as Ada Lovelace noted long ago\nan unrelated clean line\n")
        r = run_scan(identity_repo, "--staged")
        assert r.returncode == 0, r.stderr

    def test_an_added_leaking_line_blocks_at_its_own_line(
            self, identity_repo):
        commit(identity_repo, "a.md", "clean seed line\n", msg="seed")
        stage(identity_repo, "a.md", "clean seed line\nadded by Ada Lovelace\n")
        r = run_scan(identity_repo, "--staged")
        assert r.returncode == 1, r.stderr
        assert "a.md:2" in r.stderr, r.stderr

    def test_visibility_is_not_consulted_at_commit(self, identity_repo):
        # A commit is history whoever can see the remote. The JSON reports the
        # decision so the block is distinguishable from a public-remote block.
        host = socket.gethostname().split(".")[0]
        stage(identity_repo, "a.md", f"host {host}\n")
        r = run_scan(identity_repo, "--staged", "--json")
        payload = json.loads(r.stdout)
        assert payload["visibility"].startswith("not consulted")
        assert payload["blocking"], "nothing blocked"


class TestTheCommitMessageGate:
    def test_a_message_naming_the_user_is_refused(self, identity_repo):
        msg = identity_repo / "msg.txt"
        msg.write_text("fix thanks to Ada Lovelace\n")
        r = run_scan(identity_repo, "--message", str(msg))
        assert r.returncode == 1, r.stderr
        assert "env-marker" in r.stderr

    def test_a_credential_in_a_message_is_refused(self, identity_repo):
        msg = identity_repo / "msg.txt"
        msg.write_text("key: sk-ant-api03-" + "A" * 24 + "\n")
        r = run_scan(identity_repo, "--message", str(msg))
        assert r.returncode == 1
        assert "secret" in r.stderr

    def test_a_clean_message_passes(self, identity_repo):
        msg = identity_repo / "msg.txt"
        msg.write_text("fix: the tray ignored the release filter\n")
        r = run_scan(identity_repo, "--message", str(msg))
        assert r.returncode == 0, r.stderr


class TestRangeModeKeepsThePublicationPolicy:
    def _with_upstream(self, repo, ref):
        """Point the CURRENT branch's upstream at a local 'remote' ref.

        The branch name is read, not assumed: `git init`'s default is the
        machine's configuration, and `branch.main.*` config on a branch named
        `master` configures a branch nobody is on.
        """
        head = git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo).stdout.strip()
        git("update-ref", f"refs/remotes/origin/{head}", ref, cwd=repo)
        # A remote-tracking ref alone is not enough: @{u} resolves only when
        # the remote itself is configured, so git can validate the mapping.
        git("config", "remote.origin.url", str(repo.parent / "no-such-remote"),
            cwd=repo)
        git("config", "remote.origin.fetch",
            "+refs/heads/*:refs/remotes/origin/*", cwd=repo)
        git("config", f"branch.{head}.remote", "origin", cwd=repo)
        git("config", f"branch.{head}.merge", f"refs/heads/{head}", cwd=repo)

    def test_old_contamination_does_not_block_a_clean_push(
            self, identity_repo):
        commit(identity_repo, "a.md", "as Ada Lovelace noted\n", msg="old")
        commit(identity_repo, "b.md", "a clean new file\n", msg="new")
        self._with_upstream(identity_repo, "HEAD~1")   # range = b.md only
        r = run_scan(identity_repo)
        assert r.returncode == 0, r.stderr

    def test_but_a_range_that_adds_the_name_still_reports(
            self, identity_repo):
        commit(identity_repo, "a.md", "clean\n", msg="seed")
        commit(identity_repo, "b.md", "clean too\n", msg="mid")
        self._with_upstream(identity_repo, "HEAD~1")   # range = mid..HEAD
        commit(identity_repo, "c.md", "noted by Ada Lovelace\n", msg="new")
        r = run_scan(identity_repo)
        assert r.returncode == 1, r.stderr
        assert "env-marker" in r.stderr


class TestTheInstaller:
    def test_fresh_repo_gets_all_three_hooks_then_reports_in_place(
            self, identity_repo):
        r1 = run_scan(identity_repo, "--install-hooks")
        assert r1.returncode == 0, r1.stderr
        hooks = identity_repo / ".git" / "hooks"
        for name in ("pre-commit", "commit-msg", "pre-push"):
            p = hooks / name
            assert p.exists(), name
            assert os.access(p, os.X_OK), f"{name} not executable"
            first = p.read_text(encoding="utf-8").splitlines()[0]
            assert first == "#!/usr/bin/env bash"
        r2 = run_scan(identity_repo, "--install-hooks")
        assert "in place" in r2.stdout
        assert "wrote" not in r2.stdout, "a re-run must not rewrite"

    def test_a_hand_written_hook_is_never_touched(self, identity_repo):
        hooks = identity_repo / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / "pre-commit").write_text("#!/bin/sh\necho mine\n")
        r = run_scan(identity_repo, "--install-hooks")
        assert r.returncode == 0
        assert "LEFT UNTOUCHED" in r.stdout
        assert (hooks / "pre-commit").read_text() == "#!/bin/sh\necho mine\n"


class TestTheHookBindsCommits:
    """The PreToolUse gate's commit branch — the half that binds an agent even
    if it reaches for --no-verify or core.hooksPath."""

    @pytest.fixture
    def commit_repos(self, tmp_path):
        """A repo with fictional identity; nothing staged, one commit in."""
        r = tmp_path / "proj"
        r.mkdir()
        git("init", "-q", cwd=r)
        git("config", "user.email", "ada.lovelace@example.com", cwd=r)
        git("config", "user.name", "Ada Lovelace", cwd=r)
        (r / "a.md").write_text("clean\n")
        git("add", "-A", cwd=r)
        git("commit", "-q", "-m", "seed", cwd=r)
        home = tmp_path / "home"
        cfg = home / ".config" / "set-core"
        cfg.mkdir(parents=True)
        (cfg / "projects.json").write_text(json.dumps({"projects": {}}))
        return r, home

    def test_a_leaking_message_is_blocked_before_git_runs(
            self, commit_repos):
        repo, home = commit_repos
        r = _hook(repo, "git commit -m 'noted by Ada Lovelace'", home)
        assert r.returncode == 2, r.stdout + r.stderr

    def test_leaking_staged_content_is_blocked(self, commit_repos):
        repo, home = commit_repos
        (repo / "b.md").write_text(f"server {socket.gethostname()} \n")
        git("add", "b.md", cwd=repo)
        r = _hook(repo, "git commit -m 'wip'", home)
        assert r.returncode == 2, r.stdout + r.stderr

    def test_a_config_override_form_is_still_a_commit(self, commit_repos):
        # `git -c core.hooksPath=/dev/null commit` walked past the first
        # version of PUBLISH_RX and created the commit this gate exists to
        # refuse — measured live on 2026-09-08. The two-token `-c`/`-C`
        # option forms must gate like plain `git commit` does.
        repo, home = commit_repos
        (repo / "b.md").write_text(f"server {socket.gethostname()} \n")
        git("add", "b.md", cwd=repo)
        r = _hook(
            repo, "git -c core.hooksPath=/dev/null commit -m 'wip'", home)
        assert r.returncode == 2, r.stdout + r.stderr

    def test_a_cd_prefix_is_not_the_finding(self, commit_repos):
        # The whole command string is never scanned: a `cd /home/<user>/...`
        # prefix in a compound command must not become the finding.
        repo, home = commit_repos
        r = _hook(
            repo,
            f"cd /home/{getpass.getuser()}/no-such-dir 2>/dev/null; "
            f"git commit -m 'clean message'",
            home)
        assert r.returncode == 0, r.stdout + r.stderr

    def test_a_heredoc_writing_about_committing_is_not_a_commit(
            self, commit_repos):
        repo, home = commit_repos
        cmd = "cat > t.py <<'XEOF'\nrun('git commit -m x')\nXEOF"
        r = _hook(repo, cmd, home)
        assert r.returncode == 0, r.stdout + r.stderr

    def test_a_clean_commit_passes(self, commit_repos):
        repo, home = commit_repos
        r = _hook(repo, "git commit -m 'clean message'", home)
        assert r.returncode == 0, r.stdout + r.stderr


class TestPublishRxSeesEveryCommitShape:
    """Regex-level, because the failure mode is 'the hook never ran at all' —
    a dead end-to-end assertion (rc 0 with no output) looks identical to the
    bypass it was meant to catch."""

    @staticmethod
    def _mod():
        from importlib.machinery import SourceFileLoader
        return SourceFileLoader("hook_mod", str(HOOK)).load_module()

    def test_the_two_token_option_forms_match(self):
        rx = self._mod().PUBLISH_RX
        assert rx.search("git -c core.hooksPath=/dev/null commit -m x")
        assert rx.search("git -c commit.gpgsign=false commit -m x")
        assert rx.search("git -C /somewhere push origin main")

    def test_the_single_token_forms_still_match(self):
        rx = self._mod().PUBLISH_RX
        assert rx.search("git push origin main")
        assert rx.search("git --no-verify commit -m x")
        assert rx.search("cd /x && git push")

    def test_non_publishing_git_commands_do_not_match(self):
        rx = self._mod().PUBLISH_RX
        assert not rx.search("git status")
        assert not rx.search("git log --oneline")
        assert not rx.search("echo 'git push later'")


class TestASyntheticPhoneNumberIsNotSomebodysNumber:
    """101 of 101 phone findings across two public repos were E.164 examples and
    demo data. A gate wrong that often is a gate nobody reads — and it loses the
    one real number it exists to find."""

    # Every fixture below is ASSEMBLED FROM PARTS rather than written out.
    # A literal phone number in this file is a phone number in the repository,
    # and the gate — correctly — refused a push because of the first version of
    # these very tests. The measurement sitting inside the corpus it measures,
    # for the third time in one day; the cheap answer is not to write the shape.
    @staticmethod
    def _n(*parts):
        return "".join(parts)

    def _mod(self):
        from importlib.machinery import SourceFileLoader
        return SourceFileLoader("leakscan_mod", str(SCANNER)).load_module()

    def test_placeholders_are_recognised(self):
        mod = self._mod()
        cases = [
            self._n("3630", "123", "4567"),   # an ascending run
            self._n("3630", "100", "0001"),   # four of a kind
            self._n("3630", "555", "1234"),   # reserved-for-fiction prefix
            self._n("3630", "111", "2222"),   # four of a kind, mid-number
        ]
        for digits in cases:
            assert mod._looks_synthetic(digits), digits

    def test_an_ordinary_number_is_not(self):
        mod = self._mod()
        cases = [
            self._n("3620", "938", "4176"),
            self._n("3620", "473", "8291"),
        ]
        for digits in cases:
            assert not mod._looks_synthetic(digits), digits


class TestThePushGateScansWhatThePushPublishes:
    """Two holes measured on 2026-09-08, both failing in the publish direction:

    the pre-push hook derived its range from @{u}, which is unset exactly on
    the FIRST push of a branch — the push that carries every commit — so a
    leaking HEAD pushed unscanned; and an unresolvable range (a stale remote
    ref, a typo) made `git diff` fail into an empty stdout, which reported
    clean. The instrument hit the wall it was built to measure and returned
    a zero, twice in one gate.
    """

    ZEROS = "0" * 40

    @pytest.fixture
    def push_repo(self, tmp_path):
        """A clone with fictional identity, a real origin to merge-base
        against, and the installer's hooks in place."""
        origin = tmp_path / "origin"
        origin.mkdir()
        git("init", "-q", "-b", "main", cwd=origin)
        git("config", "user.email", "ada.lovelace@example.com", cwd=origin)
        git("config", "user.name", "Ada Lovelace", cwd=origin)
        (origin / "seed.md").write_text("seed\n")
        git("add", "-A", cwd=origin)
        git("commit", "-q", "-m", "seed", cwd=origin)

        clone = tmp_path / "clone"
        git("clone", "-q", str(origin), str(clone), cwd=tmp_path)
        git("config", "user.email", "ada.lovelace@example.com", cwd=clone)
        git("config", "user.name", "Ada Lovelace", cwd=clone)
        r = run_scan(clone, "--install-hooks")
        assert r.returncode == 0, r.stderr
        return clone

    def _pre_push(self, repo, *lines):
        home = repo.parent / "home"
        return subprocess.run(
            [str(repo / ".git" / "hooks" / "pre-push")],
            cwd=repo, input="".join(line + "\n" for line in lines),
            capture_output=True, text=True,
            env=dict(os.environ, HOME=str(home)))

    def _commit(self, repo, name, body, msg):
        # The hook bypass is deliberate, not a workaround being smuggled in:
        # these tests exercise the PRE-PUSH gate, and the installed pre-commit
        # gate refusing the setup commit is the other gate doing its job.
        (repo / name).write_text(body)
        git("add", name, cwd=repo)
        git("-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", msg,
            cwd=repo)

    def test_the_first_push_of_a_new_branch_is_scanned(self, push_repo):
        # rsha all zeros and no upstream: the old derivation produced
        # HEAD..HEAD here and scanned nothing while everything was publishing.
        git("checkout", "-q", "-b", "feature", cwd=push_repo)
        self._commit(push_repo, "leak.md", "noted by Ada Lovelace\n", msg="add")
        lsha = git("rev-parse", "HEAD", cwd=push_repo).stdout.strip()
        r = self._pre_push(
            push_repo,
            f"refs/heads/feature {lsha} refs/heads/feature {self.ZEROS}")
        assert r.returncode == 1, r.stdout + r.stderr
        assert "env-marker" in r.stderr

    def test_a_new_branch_with_no_common_history_is_announced_blind_not_silent(
            self, identity_repo):
        # No remote ref to merge-base against: the whole-tree checks still run
        # and still block, but the env-marker category is line-addition-based
        # and has no base to measure. The one thing it may not do is fold that
        # gap into a clean result — a leak the size of one word must not ride
        # on a warning nobody printed.
        r = run_scan(identity_repo, "--install-hooks")
        assert r.returncode == 0, r.stderr
        self._commit(identity_repo, "leak.md", "as Ada Lovelace noted\n",
                     msg="add")
        lsha = git("rev-parse", "HEAD", cwd=identity_repo).stdout.strip()
        r = self._pre_push(
            identity_repo,
            f"refs/heads/main {lsha} refs/heads/main {self.ZEROS}")
        assert "blind for this push" in r.stderr, r.stdout + r.stderr

    def test_an_ordinary_push_keeps_its_exact_range(self, push_repo):
        self._commit(push_repo, "leak.md", "noted by Ada Lovelace\n", msg="add")
        lsha = git("rev-parse", "HEAD", cwd=push_repo).stdout.strip()
        rsha = git("rev-parse", "@{u}", cwd=push_repo).stdout.strip()
        r = self._pre_push(
            push_repo, f"refs/heads/main {lsha} refs/heads/main {rsha}")
        assert r.returncode == 1, r.stdout + r.stderr

    def test_a_clean_push_still_passes(self, push_repo):
        self._commit(push_repo, "ok.md", "a clean line\n", msg="add")
        lsha = git("rev-parse", "HEAD", cwd=push_repo).stdout.strip()
        rsha = git("rev-parse", "@{u}", cwd=push_repo).stdout.strip()
        r = self._pre_push(
            push_repo, f"refs/heads/main {lsha} refs/heads/main {rsha}")
        assert r.returncode == 0, r.stdout + r.stderr

    def test_a_push_that_only_deletes_publishes_nothing(self, push_repo):
        r = self._pre_push(
            push_repo,
            f"refs/heads/gone {self.ZEROS} refs/heads/gone "
            f"{git('rev-parse', 'HEAD', cwd=push_repo).stdout.strip()}")
        assert r.returncode == 0, r.stdout + r.stderr

    def test_an_unresolvable_range_refuses_blind(self, identity_repo):
        # A stale remote ref or a typo made `git diff` fail into an empty
        # stdout, which the old code reported as a clean, zero-file scan.
        r = run_scan(identity_repo, "--range", "refs/heads/nope..HEAD")
        assert r.returncode == 2, r.stdout + r.stderr
        assert "refus" in r.stderr.lower(), r.stderr

    def test_an_empty_but_valid_range_is_still_clean(self, identity_repo):
        # The refusal is for a range that cannot RESOLVE, not for one that
        # resolves to nothing — a no-op push publishes nothing.
        commit(identity_repo, "ok.md", "clean\n", msg="seed")
        r = run_scan(identity_repo, "--range", "HEAD..HEAD")
        assert r.returncode == 0, r.stderr
