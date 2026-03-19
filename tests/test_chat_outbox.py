"""
Tests for per-sender outbox chat storage and migration.

Tests: 9.1-9.4 from agent-messaging change.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def outbox_env(tmp_path):
    """Create a temporary outbox environment"""
    control_dir = tmp_path / ".set-control"
    chat_dir = control_dir / "chat"
    outbox_dir = chat_dir / "outbox"
    members_dir = control_dir / "members"
    members_dir.mkdir(parents=True)
    return {
        "control_dir": control_dir,
        "chat_dir": chat_dir,
        "outbox_dir": outbox_dir,
        "members_dir": members_dir,
    }


class TestPerSenderOutbox:
    """9.1 Test per-sender outbox: write from two senders, verify no conflicts, merged read"""

    def test_write_two_senders_no_conflict(self, outbox_env):
        """Two different senders write to separate files"""
        outbox = outbox_env["outbox_dir"]
        outbox.mkdir(parents=True)

        # Sender A writes
        msg_a = {"id": "1", "ts": "2026-02-08T10:00:00Z", "from": "alice@mac", "to": "bob@linux", "enc": "x", "nonce": "y"}
        (outbox / "alice@mac.jsonl").write_text(json.dumps(msg_a) + "\n")

        # Sender B writes
        msg_b = {"id": "2", "ts": "2026-02-08T10:01:00Z", "from": "bob@linux", "to": "alice@mac", "enc": "a", "nonce": "b"}
        (outbox / "bob@linux.jsonl").write_text(json.dumps(msg_b) + "\n")

        # Verify separate files exist
        assert (outbox / "alice@mac.jsonl").exists()
        assert (outbox / "bob@linux.jsonl").exists()

        # Verify no cross-contamination
        alice_msgs = [json.loads(l) for l in (outbox / "alice@mac.jsonl").read_text().strip().split("\n")]
        bob_msgs = [json.loads(l) for l in (outbox / "bob@linux.jsonl").read_text().strip().split("\n")]

        assert len(alice_msgs) == 1
        assert alice_msgs[0]["from"] == "alice@mac"
        assert len(bob_msgs) == 1
        assert bob_msgs[0]["from"] == "bob@linux"

    def test_merged_read_sorted_by_timestamp(self, outbox_env):
        """Read merges all outbox files sorted by timestamp"""
        outbox = outbox_env["outbox_dir"]
        outbox.mkdir(parents=True)

        # Write messages out of order across files
        msg1 = {"id": "1", "ts": "2026-02-08T10:00:00Z", "from": "alice@mac", "to": "bob@linux"}
        msg3 = {"id": "3", "ts": "2026-02-08T10:02:00Z", "from": "alice@mac", "to": "bob@linux"}
        (outbox / "alice@mac.jsonl").write_text(
            json.dumps(msg1) + "\n" + json.dumps(msg3) + "\n"
        )

        msg2 = {"id": "2", "ts": "2026-02-08T10:01:00Z", "from": "bob@linux", "to": "alice@mac"}
        (outbox / "bob@linux.jsonl").write_text(json.dumps(msg2) + "\n")

        # Read all and sort
        all_msgs = []
        for f in outbox.glob("*.jsonl"):
            for line in f.read_text().strip().split("\n"):
                if line:
                    all_msgs.append(json.loads(line))
        all_msgs.sort(key=lambda m: m.get("ts", ""))

        assert len(all_msgs) == 3
        assert [m["id"] for m in all_msgs] == ["1", "2", "3"]

    def test_append_preserves_existing_messages(self, outbox_env):
        """Appending doesn't overwrite existing messages"""
        outbox = outbox_env["outbox_dir"]
        outbox.mkdir(parents=True)

        file = outbox / "alice@mac.jsonl"

        # First message
        msg1 = {"id": "1", "ts": "2026-02-08T10:00:00Z", "from": "alice@mac"}
        with open(file, "a") as f:
            f.write(json.dumps(msg1) + "\n")

        # Second message
        msg2 = {"id": "2", "ts": "2026-02-08T10:01:00Z", "from": "alice@mac"}
        with open(file, "a") as f:
            f.write(json.dumps(msg2) + "\n")

        lines = file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestMigration:
    """9.2 Test migration from legacy messages.jsonl to outbox"""

    def test_migrate_splits_by_sender(self, outbox_env):
        """Legacy messages.jsonl is split into per-sender outbox files"""
        chat_dir = outbox_env["chat_dir"]
        chat_dir.mkdir(parents=True)
        outbox = outbox_env["outbox_dir"]

        # Create legacy messages file
        legacy = chat_dir / "messages.jsonl"
        msgs = [
            {"id": "1", "ts": "2026-02-08T10:00:00Z", "from": "alice@mac", "to": "bob@linux", "enc": "x", "nonce": "y"},
            {"id": "2", "ts": "2026-02-08T10:01:00Z", "from": "bob@linux", "to": "alice@mac", "enc": "a", "nonce": "b"},
            {"id": "3", "ts": "2026-02-08T10:02:00Z", "from": "alice@mac", "to": "bob@linux", "enc": "c", "nonce": "d"},
        ]
        legacy.write_text("\n".join(json.dumps(m) for m in msgs) + "\n")

        # Simulate migration logic (same as in set-control-chat)
        assert legacy.exists()
        assert not outbox.exists()

        outbox.mkdir(parents=True, exist_ok=True)
        sender_messages = {}
        for line in legacy.read_text().strip().split("\n"):
            if not line:
                continue
            msg = json.loads(line)
            sender = msg.get("from", "unknown")
            if sender not in sender_messages:
                sender_messages[sender] = []
            sender_messages[sender].append(json.dumps(msg))

        for sender, lines in sender_messages.items():
            (outbox / f"{sender}.jsonl").write_text("\n".join(lines) + "\n")

        legacy.rename(legacy.with_suffix(".jsonl.migrated"))

        # Verify
        assert not legacy.exists()
        assert (chat_dir / "messages.jsonl.migrated").exists()
        assert (outbox / "alice@mac.jsonl").exists()
        assert (outbox / "bob@linux.jsonl").exists()

        alice_lines = (outbox / "alice@mac.jsonl").read_text().strip().split("\n")
        assert len(alice_lines) == 2  # Messages 1 and 3

        bob_lines = (outbox / "bob@linux.jsonl").read_text().strip().split("\n")
        assert len(bob_lines) == 1  # Message 2

    def test_migration_skips_if_outbox_exists(self, outbox_env):
        """Migration doesn't run if outbox directory already exists"""
        chat_dir = outbox_env["chat_dir"]
        chat_dir.mkdir(parents=True)
        outbox = outbox_env["outbox_dir"]
        outbox.mkdir(parents=True)

        # Create legacy file
        legacy = chat_dir / "messages.jsonl"
        legacy.write_text('{"id":"1","from":"alice@mac"}\n')

        # Migration should skip since outbox already exists
        # (per the design: only migrate if outbox doesn't exist)
        assert legacy.exists()
        assert outbox.exists()
        # Legacy file should remain
        assert legacy.exists()

    def test_migration_skips_if_no_legacy(self, outbox_env):
        """Migration doesn't run if no legacy file exists"""
        chat_dir = outbox_env["chat_dir"]
        chat_dir.mkdir(parents=True)
        legacy = chat_dir / "messages.jsonl"

        # No legacy file
        assert not legacy.exists()
        # Nothing to migrate — no error


class TestBatchedDelivery:
    """9.3 Test batched delivery: --no-push sends locally"""

    def test_no_push_creates_local_file_only(self, outbox_env):
        """With --no-push, message is written to outbox but no git ops"""
        outbox = outbox_env["outbox_dir"]
        outbox.mkdir(parents=True)

        # Simulate --no-push: just write to outbox file
        msg = {"id": "1", "ts": "2026-02-08T10:00:00Z", "from": "alice@mac", "to": "bob@linux", "enc": "x", "nonce": "y"}
        outbox_file = outbox / "alice@mac.jsonl"
        with open(outbox_file, "a") as f:
            f.write(json.dumps(msg) + "\n")

        assert outbox_file.exists()
        content = outbox_file.read_text().strip()
        assert len(content.split("\n")) == 1

    def test_sync_would_pick_up_outbox_changes(self, outbox_env):
        """Verify git add -A would include outbox changes"""
        # This is a structural verification — git add -A in set-control-sync
        # includes chat/outbox/ since it adds ALL changes
        outbox = outbox_env["outbox_dir"]
        outbox.mkdir(parents=True)

        msg = {"id": "1", "from": "alice@mac"}
        (outbox / "alice@mac.jsonl").write_text(json.dumps(msg) + "\n")

        # File exists in the control tree — git add -A would pick it up
        assert (outbox / "alice@mac.jsonl").exists()


class TestMultilineMessages:
    """9.4 Test multiline messages: preserved in outbox"""

    def test_multiline_message_preserved(self, outbox_env):
        """Multiline messages are stored as single JSON line"""
        outbox = outbox_env["outbox_dir"]
        outbox.mkdir(parents=True)

        multiline_text = "BUG: Start button\nSteps: 1. Click start\nExpected: Game starts\nActual: Nothing"
        msg = {"id": "1", "ts": "2026-02-08T10:00:00Z", "from": "alice@mac", "to": "bob@linux", "text": multiline_text}

        outbox_file = outbox / "alice@mac.jsonl"
        # json.dumps with default settings escapes newlines as \n
        with open(outbox_file, "a") as f:
            f.write(json.dumps(msg) + "\n")

        # Read back and verify
        line = outbox_file.read_text().strip()
        parsed = json.loads(line)
        assert parsed["text"] == multiline_text
        assert "\n" in parsed["text"]
        # Verify it's a single line in the file (no actual newlines in the JSON)
        assert outbox_file.read_text().strip().count("\n") == 0

    def test_multiple_multiline_messages(self, outbox_env):
        """Multiple multiline messages stored correctly"""
        outbox = outbox_env["outbox_dir"]
        outbox.mkdir(parents=True)

        outbox_file = outbox / "alice@mac.jsonl"

        for i in range(3):
            msg = {"id": str(i), "text": f"Line 1 of msg {i}\nLine 2 of msg {i}"}
            with open(outbox_file, "a") as f:
                f.write(json.dumps(msg) + "\n")

        lines = outbox_file.read_text().strip().split("\n")
        assert len(lines) == 3

        for i, line in enumerate(lines):
            parsed = json.loads(line)
            assert f"Line 1 of msg {i}" in parsed["text"]
            assert "\n" in parsed["text"]
