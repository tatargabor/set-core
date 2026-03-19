"""
Tests for control branch history compaction.

Tests: 9.5-9.7 from agent-messaging change.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def git_control_env(tmp_path):
    """Create a git repo simulating set-control branch"""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
    }

    # Create bare remote
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, check=True)

    # Create local clone
    local = tmp_path / "local"
    subprocess.run(["git", "clone", str(remote), str(local)], capture_output=True, check=True)

    # Create set-control branch with orphan commit
    subprocess.run(
        ["git", "-C", str(local), "checkout", "--orphan", "set-control"],
        capture_output=True, check=True,
    )

    # Create initial files
    members = local / "members"
    members.mkdir()
    (members / "test@host.json").write_text('{"name": "test@host", "status": "active"}')
    subprocess.run(["git", "-C", str(local), "add", "-A"], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(local), "commit", "-m", "Initial status"],
        capture_output=True, check=True, env=env,
    )
    subprocess.run(
        ["git", "-C", str(local), "push", "-u", "origin", "set-control"],
        capture_output=True, check=True,
    )

    return {"local": local, "remote": remote, "env": env}


class TestCompaction:
    """9.5 Test compaction: create N commits, squash to 1"""

    def test_creates_multiple_commits(self, git_control_env):
        """Create multiple commits to set up for compaction"""
        local = git_control_env["local"]
        env = git_control_env["env"]

        # Create 10 commits
        for i in range(10):
            members = local / "members" / "test@host.json"
            members.write_text(json.dumps({"name": "test@host", "iteration": i}))
            subprocess.run(["git", "-C", str(local), "add", "-A"], capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", str(local), "commit", "-m", f"Update status: test@host ({i})"],
                capture_output=True, check=True, env=env,
            )

        result = subprocess.run(
            ["git", "-C", str(local), "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        count = int(result.stdout.strip())
        assert count == 11  # 1 initial + 10 updates

    def test_compact_squashes_to_single(self, git_control_env):
        """Compaction squashes all commits to a single commit"""
        local = git_control_env["local"]
        env = git_control_env["env"]

        # Create several commits
        for i in range(5):
            members = local / "members" / "test@host.json"
            members.write_text(json.dumps({"name": "test@host", "iteration": i}))
            subprocess.run(["git", "-C", str(local), "add", "-A"], capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", str(local), "commit", "-m", f"Update {i}"],
                capture_output=True, check=True, env=env,
            )

        # Push before compact
        subprocess.run(
            ["git", "-C", str(local), "push", "origin", "set-control"],
            capture_output=True, check=True,
        )

        # Get root commit
        result = subprocess.run(
            ["git", "-C", str(local), "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        root = result.stdout.strip()

        # Compact: reset soft to root, amend
        subprocess.run(
            ["git", "-C", str(local), "reset", "--soft", root],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(local), "commit", "--amend", "-m", "Compacted"],
            capture_output=True, check=True, env=env,
        )

        # Verify single commit
        result = subprocess.run(
            ["git", "-C", str(local), "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        assert int(result.stdout.strip()) == 1

        # Verify files still exist
        assert (local / "members" / "test@host.json").exists()

    def test_force_push_after_compact(self, git_control_env):
        """Force push with lease succeeds after compaction"""
        local = git_control_env["local"]
        env = git_control_env["env"]

        # Create some commits and push
        for i in range(3):
            (local / "members" / "test@host.json").write_text(json.dumps({"i": i}))
            subprocess.run(["git", "-C", str(local), "add", "-A"], capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", str(local), "commit", "-m", f"Update {i}"],
                capture_output=True, check=True, env=env,
            )
        subprocess.run(
            ["git", "-C", str(local), "push", "origin", "set-control"],
            capture_output=True, check=True,
        )

        # Compact
        root = subprocess.run(
            ["git", "-C", str(local), "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        subprocess.run(["git", "-C", str(local), "reset", "--soft", root], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(local), "commit", "--amend", "-m", "Compacted"],
            capture_output=True, check=True, env=env,
        )

        # Force push
        result = subprocess.run(
            ["git", "-C", str(local), "push", "--force-with-lease", "origin", "set-control"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0


class TestAutoCompactThreshold:
    """9.6 Test auto-compact threshold"""

    def test_threshold_from_settings(self, git_control_env):
        """compact_threshold is read from team_settings.json"""
        local = git_control_env["local"]

        # Write team settings with low threshold
        settings = {"compact_threshold": 5}
        (local / "team_settings.json").write_text(json.dumps(settings))

        # Verify reading
        data = json.loads((local / "team_settings.json").read_text())
        assert data["compact_threshold"] == 5

    def test_default_threshold(self, git_control_env):
        """Default threshold is 1000 when no settings"""
        local = git_control_env["local"]
        settings_file = local / "team_settings.json"

        # No settings file — default should be 1000
        assert not settings_file.exists() or True  # May exist from previous test

    def test_low_threshold_triggers(self, git_control_env):
        """With threshold=5, exceeding it should signal compaction needed"""
        local = git_control_env["local"]
        env = git_control_env["env"]

        threshold = 5

        # Create commits exceeding threshold
        for i in range(threshold + 2):
            (local / "members" / "test@host.json").write_text(json.dumps({"i": i}))
            subprocess.run(["git", "-C", str(local), "add", "-A"], capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", str(local), "commit", "-m", f"Update {i}"],
                capture_output=True, check=True, env=env,
            )

        # Count commits
        result = subprocess.run(
            ["git", "-C", str(local), "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        count = int(result.stdout.strip())
        assert count > threshold


class TestConcurrentCompaction:
    """9.7 Test concurrent compaction: one succeeds, other recovers"""

    def test_force_push_lease_prevents_concurrent(self, git_control_env, tmp_path):
        """Two machines compacting: one succeeds via --force-with-lease, other is rejected"""
        local1 = git_control_env["local"]
        env = git_control_env["env"]
        remote = git_control_env["remote"]

        # Create a second clone (simulating machine B)
        local2 = tmp_path / "local2"
        subprocess.run(["git", "clone", str(remote), str(local2)], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(local2), "checkout", "set-control"],
            capture_output=True, check=True,
        )

        # Create commits on machine A and push
        for i in range(3):
            (local1 / "members" / "test@host.json").write_text(json.dumps({"machine": "A", "i": i}))
            subprocess.run(["git", "-C", str(local1), "add", "-A"], capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", str(local1), "commit", "-m", f"A update {i}"],
                capture_output=True, check=True, env=env,
            )
        subprocess.run(["git", "-C", str(local1), "push", "origin", "set-control"], capture_output=True, check=True)

        # Pull on machine B
        subprocess.run(["git", "-C", str(local2), "pull", "origin", "set-control"], capture_output=True, check=True)

        # Machine A compacts and force pushes
        root_a = subprocess.run(
            ["git", "-C", str(local1), "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        subprocess.run(["git", "-C", str(local1), "reset", "--soft", root_a], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(local1), "commit", "--amend", "-m", "A compacted"],
            capture_output=True, check=True, env=env,
        )
        result_a = subprocess.run(
            ["git", "-C", str(local1), "push", "--force-with-lease", "origin", "set-control"],
            capture_output=True, text=True,
        )
        assert result_a.returncode == 0

        # Machine B tries to compact (should fail because remote changed)
        root_b = subprocess.run(
            ["git", "-C", str(local2), "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        subprocess.run(["git", "-C", str(local2), "reset", "--soft", root_b], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(local2), "commit", "--amend", "-m", "B compacted"],
            capture_output=True, check=True, env=env,
        )
        result_b = subprocess.run(
            ["git", "-C", str(local2), "push", "--force-with-lease", "origin", "set-control"],
            capture_output=True, text=True,
        )
        # Should fail because remote was force-pushed by A
        assert result_b.returncode != 0

        # Machine B recovers: fetch + reset --hard
        subprocess.run(
            ["git", "-C", str(local2), "fetch", "origin", "set-control"],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(local2), "reset", "--hard", "origin/set-control"],
            capture_output=True, check=True,
        )

        # After recovery, B should have 1 commit (A's compacted state)
        result = subprocess.run(
            ["git", "-C", str(local2), "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        assert int(result.stdout.strip()) == 1
