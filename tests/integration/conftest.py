"""Fixtures for orchestration integration tests.

Provides real git repos, stub CLIs, and state file helpers.
All tests use tmp_path — fully isolated, no LLM calls.
"""

import json
import os
from pathlib import Path

import pytest

from tests.integration.helpers import run_git


FIXTURES_DIR = Path(__file__).parent / "fixtures"
STUB_BIN_DIR = FIXTURES_DIR / "bin"


@pytest.fixture
def git_repo(tmp_path):
    """Create a git repo with main branch and initial commit.

    Returns a factory: call with no args for default, or pass a Path.
    """

    def _make(repo_dir: Path | None = None) -> Path:
        repo = repo_dir or tmp_path / "project"
        repo.mkdir(parents=True, exist_ok=True)
        run_git(repo, "init", "-b", "main")
        run_git(repo, "config", "user.name", "Test")
        run_git(repo, "config", "user.email", "test@test.com")
        (repo / "README.md").write_text("initial\n")
        run_git(repo, "add", "README.md")
        run_git(repo, "commit", "-m", "initial commit")
        return repo

    return _make


@pytest.fixture
def create_branch():
    """Factory: create a feature branch with file changes.

    Usage: create_branch(repo, "feature-a", {"src/app.py": "content"})
    """

    def _make(repo: Path, name: str, files: dict[str, str]) -> str:
        branch = f"change/{name}"
        run_git(repo, "checkout", "-b", branch)
        for filepath, content in files.items():
            fpath = repo / filepath
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content)
            run_git(repo, "add", str(filepath))
        run_git(repo, "commit", "-m", f"feat: implement {name}")
        run_git(repo, "checkout", "main")
        return branch

    return _make


@pytest.fixture
def create_state_file():
    """Factory: create an orchestration-state.json file.

    Usage: create_state_file(repo, changes=[...], merge_queue=[...])
    """

    def _make(
        repo: Path,
        changes: list[dict],
        merge_queue: list[str] | None = None,
        **extras,
    ) -> Path:
        state_path = repo / "orchestration-state.json"
        state = {
            "plan_version": 1,
            "brief_hash": "test",
            "plan_phase": "initial",
            "plan_method": "api",
            "status": "running",
            "created_at": "2026-01-01T00:00:00+00:00",
            "changes": changes,
            "checkpoints": [],
            "merge_queue": merge_queue or [],
            "changes_since_checkpoint": 0,
            "last_smoke_pass_commit": "",
        }
        state.update(extras)
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        return state_path

    return _make


@pytest.fixture
def stub_env(tmp_path, monkeypatch):
    """Prepend stub bin dir to PATH and patch environment for merger.py.

    This makes merger.py find our stub set-merge/openspec/set-close
    instead of the real CLIs.
    """
    monkeypatch.setenv("PATH", f"{STUB_BIN_DIR}:{os.environ['PATH']}")
    monkeypatch.delenv("SET_MERGE_SCOPE", raising=False)
    return tmp_path
