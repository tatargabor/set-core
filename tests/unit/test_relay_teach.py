"""fleet-relay-teach: a taught rule is answered, appended to the project's taught-rules file in
its MAIN worktree, and committed alone — with real git repositories, not mocks."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from set_orch.fleet import question_relay as qr
from set_orch.fleet import relay_teach as rt

SID = "5c1d7a2e-1111-4222-8333-444455556666"
CID = "relay-5c1d7a2e-abcdef012345"
QUESTION = "Mehet élesbe a weboldal?\nA tervezet módosítás kész."
TODAY = "2026-11-24"


@pytest.fixture(autouse=True)
def live_hook(monkeypatch):
    monkeypatch.setattr(qr, "_hook_alive", lambda pid: True)


def git(root: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True,
                          env=env).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for k, v in {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                 "GIT_COMMITTER_EMAIL": "t@t"}.items():
        monkeypatch.setenv(k, v)
    root = tmp_path / "proj"
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "README.md").write_text("x\n")
    git(root, "add", "README.md")
    git(root, "commit", "-q", "-m", "init")
    return root


def waiting(base: Path, **over):
    rec = {"session_id": SID, "id": CID, "pid": os.getpid(), "questions": 1, "target": "command", **over}
    qr._write_json(qr.waiting_path(SID, base), rec)
    return rec


def delivered(base: Path):
    f = qr.answer_file(base / "answers", CID, "Q1")
    return json.loads(f.read_text())["valasz"] if f.exists() else None


def test_teach_answers_appends_and_commits_only_the_rule(repo, tmp_path):
    """AC-3 and AC-7: the answer reaches the call, the entry is verbatim, and the commit holds
    only the rules file while another session's staged file stays staged."""
    (repo / "other.txt").write_text("someone else's work\n")
    git(repo, "add", "other.txt")
    base = tmp_path / "state"
    rec = waiting(base)
    res = rt.teach(CID, "Igen, mehet", "ha a tervezet módosítás le van ellenőrizve",
                   question=QUESTION, cwd=str(repo), waiting=rec, base=base, today=TODAY)
    assert res.answered and delivered(base) == "Igen, mehet"
    assert res.written and res.commit.sha and res.commit.branch == "main" and not res.commit.reason
    assert git(repo, "show", "--name-only", "--format=", "HEAD").split() == [str(rt.RULES_REL)]
    assert git(repo, "diff", "--cached", "--name-only").split() == ["other.txt"]
    body = (repo / rt.RULES_REL).read_text()
    assert body.startswith("# Taught answers") and "## Mehet élesbe a weboldal?" in body
    assert "- **Question:** Mehet élesbe a weboldal?\n  A tervezet módosítás kész." in body
    assert "- **Answer:** Igen, mehet" in body and "ha a tervezet módosítás le van ellenőrizve" in body
    assert SID not in body and CID not in body and str(tmp_path) not in body
    assert "taught rule 2026-11-24" in git(repo, "log", "-1", "--format=%s")


def test_earlier_entries_are_never_rewritten(repo, tmp_path):
    first = rt.append_rule(repo, "Első?", "Igen", "", TODAY).read_text()
    rt.append_rule(repo, "Második?", "Nem", "mert", TODAY)
    assert (repo / rt.RULES_REL).read_text().startswith(first)
    assert "When / why" not in first


def test_a_linked_worktree_teaches_into_the_main_worktree(repo, tmp_path):
    """AC-6."""
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "feature", str(wt))
    assert rt.main_checkout(str(wt)).resolve() == repo.resolve()
    res = rt.teach(CID, "Igen", "", question="Commit?", cwd=str(wt), waiting=None, base=tmp_path / "s",
                   today=TODAY)
    assert res.commit.sha and (repo / rt.RULES_REL).is_file() and not (wt / rt.RULES_REL).exists()
    assert git(wt, "status", "--porcelain") == ""


def test_a_question_that_already_ended_is_still_taught(repo, tmp_path):
    """AC-4."""
    res = rt.teach(CID, "Igen", "", question="Commit?", cwd=str(repo), waiting=None, base=tmp_path / "s",
                   today=TODAY)
    assert not res.answered and "no longer waiting" in res.answer_reason
    assert res.written and res.commit.sha


def test_a_refusing_hook_leaves_the_rule_written_and_the_call_answered(repo, tmp_path):
    """AC-8: the hook's refusal is reported, never bypassed."""
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'blocked by the project gate' >&2\nexit 1\n")
    hook.chmod(0o755)
    base = tmp_path / "state"
    res = rt.teach(CID, "Igen", "", question="Commit?", cwd=str(repo), waiting=waiting(base), base=base,
                   today=TODAY)
    assert res.answered and delivered(base) == "Igen"
    assert res.written and not res.commit.sha and "blocked by the project gate" in res.commit.reason
    assert (repo / rt.RULES_REL).is_file() and git(repo, "log", "--format=%s").count("taught") == 0


def test_a_detached_head_is_written_but_not_committed(repo, tmp_path):
    git(repo, "checkout", "-q", "--detach")
    res = rt.teach(CID, "Igen", "", question="Commit?", cwd=str(repo), waiting=None, base=tmp_path / "s",
                   today=TODAY)
    assert res.written and not res.commit.sha and "detached HEAD" in res.commit.reason


@pytest.mark.parametrize("over,why", [({"kind": "permission"}, "permission prompt"),
                                      ({"questions": 2}, "several questions")])
def test_what_cannot_be_taught_writes_nothing(repo, tmp_path, over, why):
    """AC-5."""
    base = tmp_path / "state"
    rec = waiting(base, **over)
    assert why in rt.teachable(rec)
    res = rt.teach(CID, "Allow", "", question="Run it?", cwd=str(repo), waiting=rec, base=base, today=TODAY)
    assert not res.answered and why in res.answer_reason and not res.written
    assert not (repo / rt.RULES_REL).exists() and delivered(base) is None


def test_outside_a_git_repository_nothing_is_written(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    res = rt.teach(CID, "Igen", "", question="Q?", cwd=str(plain), waiting=None, base=tmp_path / "s", today=TODAY)
    assert not res.written and "not inside a git repository" in res.commit.reason
    assert not (plain / rt.RULES_REL).exists()


def test_the_logs_carry_no_rule_text(repo, tmp_path, caplog):
    caplog.set_level("DEBUG")
    rt.teach(CID, "Titkos válasz", "titkos feltétel", question="Titkos kérdés?", cwd=str(repo), waiting=None,
             base=tmp_path / "s", today=TODAY)
    assert caplog.records
    for text in ("Titkos", "titkos"):
        assert text not in caplog.text
