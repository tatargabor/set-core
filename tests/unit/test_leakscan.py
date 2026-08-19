"""Tests for bin/set-leakscan — the gate that refuses to publish what must not leave.

Every test here holds a shape that was WRONG at some point, not merely the
behaviour that is right. Two of them exist because the first version of the
scanner fired on them and a noisy gate is a gate that gets bypassed; one exists
because a scan that cannot see a category must say so instead of reporting zero.
"""

import getpass
import json
import os
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
