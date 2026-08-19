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
