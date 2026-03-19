"""Tests for set-memory branch tagging and migration.

Uses isolated git repos and SHODH_STORAGE per test to avoid
polluting real memory. Requires shodh-memory (skips otherwise).
"""

import json
import os
import subprocess
import tempfile

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "bin", "set-memory")

try:
    import importlib
    importlib.import_module("shodh_memory")
    HAS_SHODH = True
except ImportError:
    HAS_SHODH = False

pytestmark = pytest.mark.skipif(not HAS_SHODH, reason="shodh-memory not installed")


def run_wt(storage_path, cwd, *args, stdin=None, extra_env=None):
    """Run set-memory with isolated storage in a specific working directory."""
    env = os.environ.copy()
    env["SHODH_STORAGE"] = storage_path
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [SCRIPT, "--project", "test-branch"] + list(args),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=cwd,
        input=stdin,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def remember(storage_path, cwd, content, memory_type="Learning", tags=None):
    """Helper to store a memory."""
    tag_args = ["--tags", ",".join(tags)] if tags else []
    run_wt(storage_path, cwd, "remember", "--type", memory_type, *tag_args, stdin=content)


def list_memories(storage_path, cwd, no_migrate=False):
    """Helper to list all memories."""
    args = ["--no-migrate", "list"] if no_migrate else ["list"]
    out, _, _ = run_wt(storage_path, cwd, *args)
    return json.loads(out) if out else []


def recall(storage_path, cwd, query, limit=5, tags=None):
    """Helper to recall memories."""
    args = ["recall", query, "--limit", str(limit)]
    if tags:
        args += ["--tags", ",".join(tags)]
    out, _, _ = run_wt(storage_path, cwd, *args)
    return json.loads(out) if out else []


def git(cwd, *args):
    """Run a git command in a specific directory."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd,
    )
    return result.stdout.strip(), result.returncode


@pytest.fixture
def git_env(tmp_path):
    """Create an isolated git repo with a branch for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = tmp_path / "storage"
    storage.mkdir()

    git(str(repo), "init")
    git(str(repo), "config", "user.name", "Test User")
    git(str(repo), "config", "user.email", "test@test.com")
    # Create an initial commit so we have a branch
    (repo / "README.md").write_text("test")
    git(str(repo), "add", ".")
    git(str(repo), "commit", "-m", "init")

    return str(repo), str(storage)


@pytest.fixture
def non_git_env(tmp_path):
    """Create a non-git directory for testing."""
    workdir = tmp_path / "nogit"
    workdir.mkdir()
    storage = tmp_path / "storage"
    storage.mkdir()
    return str(workdir), str(storage)


# --- Auto-tag tests ---

class TestAutoTag:
    def test_remember_on_branch_adds_tag(self, git_env):
        """5.1: remember on a branch → verify branch:* tag present"""
        repo, storage = git_env
        # We're on the default branch (main or master)
        branch, _ = git(repo, "branch", "--show-current")

        remember(storage, repo, "test insight on branch")
        memories = list_memories(storage, repo)

        assert len(memories) == 1
        tags = memories[0].get("tags", [])
        branch_tags = [t for t in tags if t.startswith("branch:")]
        assert len(branch_tags) == 1
        assert branch_tags[0] == f"branch:{branch}"

    def test_remember_with_existing_branch_tag_no_duplicate(self, git_env):
        """5.2: remember with existing branch:custom tag → no duplicate"""
        repo, storage = git_env

        remember(storage, repo, "test with custom branch", tags=["branch:custom"])
        memories = list_memories(storage, repo)

        assert len(memories) == 1
        tags = memories[0].get("tags", [])
        branch_tags = [t for t in tags if t.startswith("branch:")]
        assert len(branch_tags) == 1
        assert branch_tags[0] == "branch:custom"

    def test_remember_outside_git_no_branch_tag(self, non_git_env):
        """5.3: remember outside git repo → no branch:* tag"""
        workdir, storage = non_git_env

        remember(storage, workdir, "test outside git")
        memories = list_memories(storage, workdir, no_migrate=True)

        assert len(memories) == 1
        tags = memories[0].get("tags", [])
        branch_tags = [t for t in tags if t.startswith("branch:")]
        assert len(branch_tags) == 0

    def test_remember_on_feature_branch(self, git_env):
        """Auto-tag uses correct branch name on feature branches."""
        repo, storage = git_env
        git(repo, "checkout", "-b", "feature/test-xyz")

        remember(storage, repo, "feature branch insight")
        memories = list_memories(storage, repo)

        assert len(memories) == 1
        tags = memories[0].get("tags", [])
        assert "branch:feature/test-xyz" in tags


# --- Recall boost tests ---

class TestRecallBoost:
    def test_recall_boost_current_branch_first(self, git_env):
        """5.4: memories with current branch tag appear first"""
        repo, storage = git_env
        branch, _ = git(repo, "branch", "--show-current")

        # Create memories with different branch tags
        remember(storage, repo, "relevant to current branch cache strategy")
        # Now add one tagged with a different branch
        run_wt(storage, repo, "remember", "--type", "Learning",
               "--tags", "branch:other/branch",
               stdin="different branch cache info")

        results = recall(storage, repo, "cache strategy", limit=5)
        assert len(results) >= 1

        # First result should be from current branch
        first_tags = results[0].get("tags", [])
        assert f"branch:{branch}" in first_tags

    def test_recall_explicit_tags_no_boost(self, git_env):
        """5.5: explicit --tags → no branch boost applied"""
        repo, storage = git_env

        remember(storage, repo, "current branch memory for auth")
        run_wt(storage, repo, "remember", "--type", "Learning",
               "--tags", "branch:other/branch,topic:auth",
               stdin="other branch auth memory")

        # Explicit tags should bypass branch boost
        results = recall(storage, repo, "auth", tags=["topic:auth"])
        # Should only get the one with topic:auth tag
        for r in results:
            assert "topic:auth" in r.get("tags", [])


# --- Migration tests ---

class TestMigration:
    def test_migration_001_adds_branch_unknown(self, git_env):
        """5.6: memories without branch tag get branch:unknown"""
        repo, storage = git_env
        storage_dir = os.path.join(storage, "test-branch")
        os.makedirs(storage_dir, exist_ok=True)

        # Create a memory directly without branch tag by using --no-migrate
        # and manually bypassing auto-tag (use non-git dir)
        non_git = os.path.realpath(os.path.join(str(git_env[0]), "..", "nogit"))
        os.makedirs(non_git, exist_ok=True)
        run_wt(storage, non_git, "--no-migrate", "remember", "--type", "Learning",
               "--tags", "source:test", stdin="pre-migration memory")

        # Verify no branch tag (use --no-migrate to avoid auto-migration)
        memories = list_memories(storage, non_git, no_migrate=True)
        assert len(memories) == 1
        assert not any(t.startswith("branch:") for t in memories[0].get("tags", []))

        # Run migration
        out, err, rc = run_wt(storage, repo, "migrate")
        assert rc == 0

        # Verify branch:unknown was added
        memories = list_memories(storage, repo, no_migrate=True)
        assert len(memories) == 1
        assert "branch:unknown" in memories[0]["tags"]
        assert "source:test" in memories[0]["tags"]

    def test_migration_001_idempotent(self, git_env):
        """5.7: running twice produces same result"""
        repo, storage = git_env
        non_git = os.path.realpath(os.path.join(str(git_env[0]), "..", "nogit"))
        os.makedirs(non_git, exist_ok=True)

        # Create memory without branch tag
        run_wt(storage, non_git, "--no-migrate", "remember", "--type", "Learning",
               stdin="idempotency test")

        # Run migration twice
        run_wt(storage, repo, "migrate")

        # Delete .migrations to force re-run
        mig_file = os.path.join(storage, "test-branch", ".migrations")
        if os.path.exists(mig_file):
            os.remove(mig_file)

        run_wt(storage, repo, "migrate")

        # Should still have exactly one branch:unknown tag
        memories = list_memories(storage, repo)
        assert len(memories) == 1
        branch_tags = [t for t in memories[0].get("tags", []) if t.startswith("branch:")]
        assert branch_tags == ["branch:unknown"]

    def test_migration_auto_run_on_first_command(self, git_env):
        """5.8: first command triggers migration, subsequent skip"""
        repo, storage = git_env
        non_git = os.path.realpath(os.path.join(str(git_env[0]), "..", "nogit"))
        os.makedirs(non_git, exist_ok=True)

        # Create memory without migration
        run_wt(storage, non_git, "--no-migrate", "remember", "--type", "Learning",
               stdin="auto-migrate test")

        # First list should trigger migration (stderr message)
        out, err, _ = run_wt(storage, repo, "list")
        assert "Migrating memory storage" in err

        # Second list should NOT trigger migration
        out, err2, _ = run_wt(storage, repo, "list")
        # The migration already ran and .migrations is set, so no migration message
        # (note: each run_wt is a separate process, but .migrations file persists)
        assert "Migrating memory storage" not in err2

    def test_no_migrate_flag(self, git_env):
        """5.9: --no-migrate flag prevents auto-migration"""
        repo, storage = git_env
        non_git = os.path.realpath(os.path.join(str(git_env[0]), "..", "nogit"))
        os.makedirs(non_git, exist_ok=True)

        # Create memory without migration
        run_wt(storage, non_git, "--no-migrate", "remember", "--type", "Learning",
               stdin="no-migrate test")

        # List with --no-migrate should NOT run migration
        out, err, _ = run_wt(storage, repo, "--no-migrate", "list")
        assert "Migrating" not in err

        # Memory should still lack branch tag
        memories = json.loads(out) if out else []
        assert len(memories) == 1
        assert not any(t.startswith("branch:") for t in memories[0].get("tags", []))

    def test_migrate_status(self, git_env):
        """5.10: set-memory migrate --status output"""
        repo, storage = git_env

        # Before any migration
        out, _, rc = run_wt(storage, repo, "migrate", "--status")
        assert rc == 0
        assert "001" in out
        assert "pending" in out

        # Run migration
        run_wt(storage, repo, "migrate")

        # After migration
        out, _, rc = run_wt(storage, repo, "migrate", "--status")
        assert rc == 0
        assert "001" in out
        assert "applied" in out
