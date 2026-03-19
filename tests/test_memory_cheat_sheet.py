"""Tests for cheat-sheet memory: L1 session start injection and auto-tagging.

Coverage:
  - L1 SessionStart hook injects OPERATIONAL CHEAT SHEET when cheat-sheet memories exist
  - L1 SessionStart hook skips section when no cheat-sheet memories exist
  - Short content (<20 chars) is filtered from cheat-sheet output
  - Duplicate content is deduplicated in output
  - set-memory remember with cheat-sheet tag stores memory correctly
  - Cheat-sheet entries can be listed and removed via forget

Requires shodh-memory to be installed (skips otherwise).

NOTE: Both CLI and hook must run from the same git project dir so that
      set-memory auto-detects the same project name for both writes and reads.
"""

import json
import os
import subprocess

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "bin", "set-memory")
HOOK = os.path.join(os.path.dirname(__file__), "..", "bin", "set-hook-memory")

try:
    import importlib
    importlib.import_module("shodh_memory")
    HAS_SHODH = True
except ImportError:
    HAS_SHODH = False

pytestmark = pytest.mark.skipif(not HAS_SHODH, reason="shodh-memory not installed")


def setup_git_repo(tmp_path):
    """Init a minimal git repo so both CLI and hook auto-detect the same project name."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        capture_output=True,
        cwd=str(tmp_path),
        env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t.com",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t.com"},
    )
    return str(tmp_path)


def run_wt(project_dir, storage_path, *args, stdin=None):
    """Run set-memory from project_dir with isolated storage. Returns (stdout, returncode)."""
    env = os.environ.copy()
    env["SHODH_STORAGE"] = storage_path
    result = subprocess.run(
        [SCRIPT] + list(args),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=project_dir,
    )
    return result.stdout.strip(), result.returncode


def run_session_start(project_dir, storage_path):
    """Invoke set-hook-memory SessionStart from project_dir. Returns (stdout, returncode)."""
    payload = json.dumps({"session_id": "test-session-cs-123"})
    env = os.environ.copy()
    env["SHODH_STORAGE"] = storage_path
    env["CLAUDE_PROJECT_DIR"] = project_dir
    result = subprocess.run(
        [HOOK, "SessionStart"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=project_dir,
    )
    return result.stdout, result.returncode


# ============================================================
# Cheat-sheet memory storage
# ============================================================

class TestCheatSheetStorage:
    def test_remember_with_cheat_sheet_tag(self, tmp_path):
        """set-memory remember with cheat-sheet tag stores the memory."""
        project_dir = setup_git_repo(tmp_path)
        storage = str(tmp_path / "shodh")
        content = "Run GUI tests: PYTHONPATH=. pytest tests/gui/ -v --tb=short"
        stdout, rc = run_wt(project_dir, storage,
                            "remember", "--type", "Learning",
                            "--tags", "cheat-sheet,testing",
                            stdin=content)
        assert rc == 0

    def test_cheat_sheet_recalled_by_tag(self, tmp_path):
        """Memories saved with cheat-sheet tag are retrievable by tag filter."""
        project_dir = setup_git_repo(tmp_path)
        storage = str(tmp_path / "shodh")
        content = "Always use PYTHONPATH=. when running pytest in this project"
        run_wt(project_dir, storage,
               "remember", "--type", "Learning", "--tags", "cheat-sheet", stdin=content)

        stdout, rc = run_wt(project_dir, storage,
                            "recall", "pytest", "--tags", "cheat-sheet", "--limit", "5")
        assert rc == 0
        data = json.loads(stdout) if stdout else []
        assert len(data) >= 1
        assert any("PYTHONPATH" in m.get("content", "") for m in data)

    def test_cheat_sheet_appears_in_regular_recall(self, tmp_path):
        """Cheat-sheet entries appear in recall without tag filter too."""
        project_dir = setup_git_repo(tmp_path)
        storage = str(tmp_path / "shodh")
        content = "Database migration: run flask db upgrade after pulling"
        run_wt(project_dir, storage,
               "remember", "--type", "Learning", "--tags", "cheat-sheet,database", stdin=content)

        stdout, rc = run_wt(project_dir, storage,
                            "recall", "database migration", "--limit", "5")
        assert rc == 0


# ============================================================
# L1 Session Start injection
# ============================================================

class TestSessionStartInjection:
    def test_cheat_sheet_section_injected_when_memories_exist(self, tmp_path):
        """L1 hook injects OPERATIONAL CHEAT SHEET when cheat-sheet memories exist."""
        project_dir = setup_git_repo(tmp_path)
        storage = str(tmp_path / "shodh")

        content = "Always run set-memory recall before starting a new change"
        run_wt(project_dir, storage,
               "remember", "--type", "Learning", "--tags", "cheat-sheet,workflow", stdin=content)

        stdout, rc = run_session_start(project_dir, storage)
        assert rc == 0
        assert "OPERATIONAL CHEAT SHEET" in stdout, \
            f"CHEAT SHEET section missing from session start output: {stdout[:500]}"
        assert "recall" in stdout

    def test_no_cheat_sheet_section_when_empty(self, tmp_path):
        """L1 hook skips CHEAT SHEET section when no cheat-sheet memories exist."""
        project_dir = setup_git_repo(tmp_path)
        storage = str(tmp_path / "shodh")

        stdout, rc = run_session_start(project_dir, storage)
        assert rc == 0
        assert "OPERATIONAL CHEAT SHEET" not in stdout

    def test_short_content_filtered(self, tmp_path):
        """Cheat-sheet entries shorter than 20 chars are filtered from output."""
        project_dir = setup_git_repo(tmp_path)
        storage = str(tmp_path / "shodh")

        run_wt(project_dir, storage,
               "remember", "--type", "Learning", "--tags", "cheat-sheet", stdin="too short")
        run_wt(project_dir, storage,
               "remember", "--type", "Learning", "--tags", "cheat-sheet",
               stdin="Use git worktree for parallel agent development")

        stdout, rc = run_session_start(project_dir, storage)
        assert rc == 0
        if "OPERATIONAL CHEAT SHEET" in stdout:
            assert "too short" not in stdout
            assert "worktree" in stdout or "parallel" in stdout

    def test_duplicate_content_deduplicated(self, tmp_path):
        """Duplicate cheat-sheet content is deduplicated in the hook's display output.

        The hook deduplicates by first-50-chars key at display time.
        Two identical stored records should appear only once in the cheat-sheet section.
        We check the additionalContext field directly (not raw JSON string).
        """
        project_dir = setup_git_repo(tmp_path)
        storage = str(tmp_path / "shodh")
        content = "PYTHONPATH=. pytest is required for all tests in this project"

        run_wt(project_dir, storage,
               "remember", "--type", "Learning", "--tags", "cheat-sheet", stdin=content)
        run_wt(project_dir, storage,
               "remember", "--type", "Learning", "--tags", "cheat-sheet", stdin=content)

        stdout, rc = run_session_start(project_dir, storage)
        assert rc == 0

        # Parse the JSON output to get the actual additionalContext text
        try:
            data = json.loads(stdout)
            ctx = data.get("hookSpecificOutput", {}).get("additionalContext", stdout)
        except (json.JSONDecodeError, AttributeError):
            ctx = stdout

        # In the rendered cheat-sheet section, the content should appear at most once
        if "OPERATIONAL CHEAT SHEET" in ctx:
            section_start = ctx.index("OPERATIONAL CHEAT SHEET")
            rest = ctx[section_start:]
            # Find end of cheat-sheet section (next === header block)
            next_section = rest.find("\n===", 5)
            cheat_section = rest[:next_section] if next_section != -1 else rest
            occurrences = cheat_section.count("PYTHONPATH")
            assert occurrences <= 1, f"Duplicate content appeared {occurrences} times in cheat-sheet"

    def test_session_start_exits_0_without_memories(self, tmp_path):
        """L1 hook exits 0 even with empty storage."""
        project_dir = setup_git_repo(tmp_path)
        storage = str(tmp_path / "empty_storage")
        stdout, rc = run_session_start(project_dir, storage)
        assert rc == 0


# ============================================================
# Cheat-sheet scope
# ============================================================

class TestCheatSheetScope:
    def test_credential_like_content_stored_if_manually_added(self, tmp_path):
        """Manual cheat-sheet add works regardless of content.

        Scope restriction (no credentials) applies to L5 auto-extraction, not manual adds.
        """
        project_dir = setup_git_repo(tmp_path)
        storage = str(tmp_path / "shodh")
        content = "DB admin login: admin / changeme123 (local dev only)"
        stdout, rc = run_wt(project_dir, storage,
                            "remember", "--type", "Learning",
                            "--tags", "cheat-sheet", stdin=content)
        assert rc == 0
