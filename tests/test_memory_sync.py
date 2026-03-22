"""Tests for set-memory sync (git-based memory sharing).

Uses isolated git repos with local bare remotes and isolated SHODH_STORAGE
per test to avoid polluting real memory or real git repos.
Requires shodh-memory to be installed (skips otherwise).
"""

import json
import os
import subprocess
import tempfile

import pytest

# Path to the set-memory script (relative to project root)
SCRIPT = os.path.join(os.path.dirname(__file__), "..", "bin", "set-memory")

# Check if shodh-memory is available
try:
    import importlib
    importlib.import_module("shodh_memory")
    HAS_SHODH = True
except ImportError:
    HAS_SHODH = False

pytestmark = pytest.mark.skipif(not HAS_SHODH, reason="shodh-memory not installed")


def run_wt(storage_path, cwd, *args, stdin=None):
    """Run set-memory with isolated storage in a specific working directory."""
    env = os.environ.copy()
    env["SHODH_STORAGE"] = storage_path
    result = subprocess.run(
        [SCRIPT, "--project", "test-sync"] + list(args),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=cwd,
        input=stdin,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def remember(storage_path, cwd, content, memory_type="Context", tags=None):
    """Helper to store a memory."""
    env = os.environ.copy()
    env["SHODH_STORAGE"] = storage_path
    tag_args = ["--tags", ",".join(tags)] if tags else []
    subprocess.run(
        [SCRIPT, "--project", "test-sync", "remember", "--type", memory_type] + tag_args,
        input=content,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=cwd,
    )


def list_memories(storage_path, cwd):
    """Helper to list all memories."""
    out, _, _ = run_wt(storage_path, cwd, "list")
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
    """Create isolated git environment: bare remote + working repo + storage dirs.

    Returns dict with:
      - remote: path to bare remote repo
      - repo_a: path to working repo (machine A)
      - repo_b: path to working repo (machine B, same remote)
      - storage_a: isolated shodh storage for machine A
      - storage_b: isolated shodh storage for machine B
    """
    remote = str(tmp_path / "remote.git")
    repo_a = str(tmp_path / "repo_a")
    repo_b = str(tmp_path / "repo_b")
    storage_a = str(tmp_path / "storage_a")
    storage_b = str(tmp_path / "storage_b")

    os.makedirs(storage_a)
    os.makedirs(storage_b)

    # Create bare remote
    subprocess.run(["git", "init", "--bare", remote], capture_output=True, timeout=10)

    # Create working repo A with an initial commit (needed for git operations)
    subprocess.run(["git", "init", repo_a], capture_output=True, timeout=10)
    subprocess.run(["git", "-C", repo_a, "config", "user.name", "alice"], capture_output=True, timeout=10)
    subprocess.run(["git", "-C", repo_a, "config", "user.email", "alice@test"], capture_output=True, timeout=10)
    with open(os.path.join(repo_a, "README.md"), "w") as f:
        f.write("test repo")
    subprocess.run(["git", "-C", repo_a, "add", "."], capture_output=True, timeout=10)
    subprocess.run(["git", "-C", repo_a, "commit", "-m", "init"], capture_output=True, timeout=10)
    subprocess.run(["git", "-C", repo_a, "remote", "add", "origin", remote], capture_output=True, timeout=10)
    subprocess.run(["git", "-C", repo_a, "push", "-u", "origin", "main"], capture_output=True, timeout=10)

    # Create working repo B by cloning
    subprocess.run(["git", "clone", remote, repo_b], capture_output=True, timeout=10)
    subprocess.run(["git", "-C", repo_b, "config", "user.name", "bob"], capture_output=True, timeout=10)
    subprocess.run(["git", "-C", repo_b, "config", "user.email", "bob@test"], capture_output=True, timeout=10)

    return {
        "remote": remote,
        "repo_a": repo_a,
        "repo_b": repo_b,
        "storage_a": storage_a,
        "storage_b": storage_b,
    }


# ── 6.1 Identity resolution ─────────────────────────────────────────────


class TestSyncIdentity:
    def test_identity_uses_git_user_and_hostname(self, git_env):
        """Identity resolves to <git-user>/<hostname> format."""
        out, _, rc = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "status")
        assert rc == 0
        # Should contain "Identity: alice/<hostname>"
        assert "Identity: alice/" in out

    def test_identity_lowercase_sanitized(self, git_env):
        """User names are lowercased and sanitized."""
        # Set a user name with spaces and uppercase
        subprocess.run(
            ["git", "-C", git_env["repo_a"], "config", "user.name", "Alice Bob"],
            capture_output=True, timeout=10,
        )
        out, _, _ = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "status")
        assert "Identity: alice-bob/" in out

    def test_different_users_different_identities(self, git_env):
        """Two users have different identities."""
        out_a, _, _ = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "status")
        out_b, _, _ = run_wt(git_env["storage_b"], git_env["repo_b"], "sync", "status")
        # Extract identity lines
        id_a = [l for l in out_a.splitlines() if l.startswith("Identity:")][0]
        id_b = [l for l in out_b.splitlines() if l.startswith("Identity:")][0]
        assert "alice" in id_a
        assert "bob" in id_b


# ── 6.2 Push tests ──────────────────────────────────────────────────────


class TestSyncPush:
    def test_first_push_creates_orphan_branch(self, git_env):
        """First push creates the set-memory orphan branch on remote."""
        remember(git_env["storage_a"], git_env["repo_a"], "test memory", "Decision")

        out, _, rc = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")
        assert rc == 0
        assert "Pushed to" in out

        # Verify branch exists on remote
        branches, _ = git(git_env["remote"], "branch")
        assert "set-memory" in branches

    def test_push_creates_user_machine_path(self, git_env):
        """Push stores file under <user>/<machine>/memories.json."""
        remember(git_env["storage_a"], git_env["repo_a"], "test memory", "Decision")

        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        # List files on the set-memory branch
        files, _ = git(git_env["remote"], "ls-tree", "-r", "--name-only", "set-memory")
        assert "memories.json" in files
        assert "alice/" in files

    def test_subsequent_push_updates_file(self, git_env):
        """Second push updates the existing file."""
        remember(git_env["storage_a"], git_env["repo_a"], "memory 1", "Decision")
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        # Add another memory
        remember(git_env["storage_a"], git_env["repo_a"], "memory 2", "Learning")
        out, _, rc = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")
        assert rc == 0
        assert "Pushed to" in out

    def test_push_skip_when_unchanged(self, git_env):
        """Push skips if nothing changed since last push."""
        remember(git_env["storage_a"], git_env["repo_a"], "static memory", "Decision")

        # First push
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        # Second push — same content
        out, _, rc = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")
        assert rc == 0
        assert "Nothing to push." in out

    def test_push_creates_sync_state(self, git_env):
        """Push creates .sync-state file with hash and timestamp."""
        remember(git_env["storage_a"], git_env["repo_a"], "test", "Decision")
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        state_file = os.path.join(git_env["storage_a"], "test-sync", ".sync-state")
        assert os.path.exists(state_file)

        state = json.loads(open(state_file).read())
        assert "last_push_hash" in state
        assert "last_push_at" in state


# ── 6.3 Pull tests ──────────────────────────────────────────────────────


class TestSyncPull:
    def test_pull_imports_from_other_user(self, git_env):
        """Pull imports memories pushed by another user."""
        # Alice pushes
        remember(git_env["storage_a"], git_env["repo_a"], "alice memory", "Decision", ["alice"])
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        # Bob pulls
        out, _, rc = run_wt(git_env["storage_b"], git_env["repo_b"], "sync", "pull")
        assert rc == 0

        # Bob should have alice's memory
        bob_memories = list_memories(git_env["storage_b"], git_env["repo_b"])
        contents = {m["content"] for m in bob_memories}
        assert "alice memory" in contents

    def test_pull_skips_own_files(self, git_env):
        """Pull does not import own pushed files (avoids self-duplication)."""
        remember(git_env["storage_a"], git_env["repo_a"], "alice memory", "Decision")
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        # Alice pulls — should find no other sources
        out, _, rc = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "pull")
        assert rc == 0
        assert "No other sources found." in out

    def test_pull_skip_when_remote_unchanged(self, git_env):
        """Pull skips import if remote hasn't changed."""
        remember(git_env["storage_a"], git_env["repo_a"], "alice memory", "Decision")
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        # Bob pulls first time
        run_wt(git_env["storage_b"], git_env["repo_b"], "sync", "pull")

        # Bob pulls again — no changes
        out, _, rc = run_wt(git_env["storage_b"], git_env["repo_b"], "sync", "pull")
        assert rc == 0
        assert "Up to date." in out

    def test_pull_no_sync_branch(self, git_env):
        """Pull with no sync branch shows helpful message."""
        out, _, rc = run_wt(git_env["storage_b"], git_env["repo_b"], "sync", "pull")
        assert rc == 0
        assert "No sync branch found" in out

    def test_pull_selective_from(self, git_env):
        """Pull with --from only imports from specified source."""
        # Alice and Bob both push
        remember(git_env["storage_a"], git_env["repo_a"], "alice memory", "Decision")
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        remember(git_env["storage_b"], git_env["repo_b"], "bob memory", "Decision")
        run_wt(git_env["storage_b"], git_env["repo_b"], "sync", "push")

        # Create a third repo/storage for carol
        repo_c = os.path.join(os.path.dirname(git_env["repo_a"]), "repo_c")
        storage_c = os.path.join(os.path.dirname(git_env["storage_a"]), "storage_c")
        os.makedirs(storage_c)
        subprocess.run(
            ["git", "clone", git_env["remote"], repo_c],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", repo_c, "config", "user.name", "carol"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", repo_c, "config", "user.email", "carol@test"],
            capture_output=True, timeout=10,
        )

        # Get alice's identity to use in --from
        status_out, _, _ = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "status")
        alice_identity = [
            l.split(": ", 1)[1] for l in status_out.splitlines()
            if l.startswith("Identity:")
        ][0]

        # Carol pulls only from alice
        out, _, rc = run_wt(storage_c, repo_c, "sync", "pull", "--from", alice_identity)
        assert rc == 0

        # Carol should only have alice's memory
        carol_memories = list_memories(storage_c, repo_c)
        contents = {m["content"] for m in carol_memories}
        assert "alice memory" in contents
        assert "bob memory" not in contents

    def test_pull_per_source_summary(self, git_env):
        """Pull prints per-source import summary."""
        remember(git_env["storage_a"], git_env["repo_a"], "alice mem", "Decision")
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        out, _, _ = run_wt(git_env["storage_b"], git_env["repo_b"], "sync", "pull")
        # Should contain source identity and counts
        assert "new" in out
        assert "skipped" in out


# ── 6.4 Sync status ─────────────────────────────────────────────────────


class TestSyncStatus:
    def test_status_never_synced(self, git_env):
        """Status shows 'Never synced.' when no prior sync."""
        out, _, rc = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "status")
        assert rc == 0
        assert "Never synced." in out

    def test_status_shows_identity(self, git_env):
        """Status shows the current identity."""
        out, _, rc = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "status")
        assert rc == 0
        assert "Identity:" in out

    def test_status_after_push(self, git_env):
        """Status shows push timestamp after push."""
        remember(git_env["storage_a"], git_env["repo_a"], "test", "Decision")
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        out, _, rc = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "status")
        assert rc == 0
        assert "Push:" in out

    def test_status_lists_remote_sources(self, git_env):
        """Status lists remote sources."""
        remember(git_env["storage_a"], git_env["repo_a"], "test", "Decision")
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        out, _, _ = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "status")
        assert "(you)" in out  # own entry marked

    def test_status_shows_other_users(self, git_env):
        """Status lists other users' sources."""
        # Both push
        remember(git_env["storage_a"], git_env["repo_a"], "test a", "Decision")
        run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "push")

        remember(git_env["storage_b"], git_env["repo_b"], "test b", "Decision")
        run_wt(git_env["storage_b"], git_env["repo_b"], "sync", "push")

        # Check status from A's perspective
        out, _, _ = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "status")
        assert "alice" in out
        assert "bob" in out


# ── 6.5 Graceful degradation ────────────────────────────────────────────


class TestSyncGracefulDegradation:
    def test_sync_not_git_repo(self, tmp_path):
        """Sync in non-git directory returns error."""
        storage = str(tmp_path / "storage")
        os.makedirs(storage)
        non_git = str(tmp_path / "not-a-repo")
        os.makedirs(non_git)

        _, err, rc = run_wt(storage, non_git, "sync", "push")
        assert rc != 0
        assert "not a git repository" in err

    def test_sync_no_remote(self, tmp_path):
        """Sync in repo without remote returns error."""
        storage = str(tmp_path / "storage")
        os.makedirs(storage)
        repo = str(tmp_path / "no-remote")
        subprocess.run(["git", "init", repo], capture_output=True, timeout=10)
        subprocess.run(
            ["git", "-C", repo, "config", "user.name", "test"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", repo, "config", "user.email", "test@test"],
            capture_output=True, timeout=10,
        )
        # Create initial commit
        with open(os.path.join(repo, "f"), "w") as f:
            f.write("x")
        subprocess.run(["git", "-C", repo, "add", "."], capture_output=True, timeout=10)
        subprocess.run(["git", "-C", repo, "commit", "-m", "init"], capture_output=True, timeout=10)

        _, err, rc = run_wt(storage, repo, "sync", "push")
        assert rc != 0
        assert "no git remote" in err

    def test_sync_unknown_subcommand(self, git_env):
        """Unknown sync subcommand returns error."""
        _, err, rc = run_wt(git_env["storage_a"], git_env["repo_a"], "sync", "bogus")
        assert rc != 0
        assert "unknown sync subcommand" in err
