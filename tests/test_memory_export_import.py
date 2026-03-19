"""Tests for set-memory export/import with deduplication.

Uses isolated SHODH_STORAGE per test to avoid polluting real memory.
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


def run_wt(storage_path, *args, stdin=None):
    """Run set-memory with isolated storage. Returns (stdout, returncode)."""
    env = os.environ.copy()
    env["SHODH_STORAGE"] = storage_path
    result = subprocess.run(
        [SCRIPT, "--project", "test-proj"] + list(args),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return result.stdout.strip(), result.returncode


def remember(storage_path, content, memory_type="Context", tags=None):
    """Helper to store a memory."""
    env = os.environ.copy()
    env["SHODH_STORAGE"] = storage_path
    tag_args = ["--tags", ",".join(tags)] if tags else []
    subprocess.run(
        [SCRIPT, "--project", "test-proj", "remember", "--type", memory_type] + tag_args,
        input=content,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def list_memories(storage_path):
    """Helper to list all memories."""
    out, _ = run_wt(storage_path, "list")
    return json.loads(out) if out else []


@pytest.fixture
def storage_a(tmp_path):
    """Isolated storage directory for project A."""
    d = tmp_path / "storage_a"
    d.mkdir()
    return str(d)


@pytest.fixture
def storage_b(tmp_path):
    """Isolated storage directory for project B."""
    d = tmp_path / "storage_b"
    d.mkdir()
    return str(d)


@pytest.fixture
def export_file(tmp_path):
    """Temp path for export file."""
    return str(tmp_path / "export.json")


# ── 3.2 Export full project ────────────────────────────────────────────


class TestExport:
    def test_export_full_project(self, storage_a, export_file):
        """Export all memories — valid JSON schema, all fields present."""
        remember(storage_a, "Decision about auth", "Decision", ["auth"])
        remember(storage_a, "Learned about caching", "Learning", ["cache"])
        remember(storage_a, "Context about deploy", "Context", ["deploy"])

        out, rc = run_wt(storage_a, "export")
        assert rc == 0

        data = json.loads(out)
        assert data["version"] == 1
        assert data["format"] == "set-memory-export"
        assert data["project"] == "test-proj"
        assert "exported_at" in data
        assert data["count"] == 3
        assert len(data["records"]) == 3

        # Check all required fields on each record
        required = {
            "id", "content", "experience_type", "tags", "importance",
            "created_at", "last_accessed", "access_count", "is_anomaly",
            "is_failure", "compressed", "metadata", "entities",
        }
        for rec in data["records"]:
            assert required.issubset(set(rec.keys())), f"Missing fields: {required - set(rec.keys())}"

    def test_export_empty_project(self, storage_a):
        """Export empty project — valid JSON, count 0."""
        out, rc = run_wt(storage_a, "export")
        assert rc == 0

        data = json.loads(out)
        assert data["version"] == 1
        assert data["format"] == "set-memory-export"
        assert data["count"] == 0
        assert data["records"] == []

    def test_export_to_file(self, storage_a, export_file):
        """Export to --output file."""
        remember(storage_a, "test content", "Context")

        out, rc = run_wt(storage_a, "export", "--output", export_file)
        assert rc == 0
        assert out == ""  # nothing on stdout

        data = json.loads(open(export_file).read())
        assert data["count"] == 1
        assert len(data["records"]) == 1


# ── 3.4–3.8 Import dedup scenarios ────────────────────────────────────


class TestImportDedup:
    def test_import_into_empty(self, storage_a, storage_b, export_file):
        """Import into empty project — all imported, original_id set."""
        remember(storage_a, "memory one", "Decision", ["tag1"])
        remember(storage_a, "memory two", "Learning", ["tag2"])

        run_wt(storage_a, "export", "--output", export_file)
        out, rc = run_wt(storage_b, "import", export_file)
        assert rc == 0

        result = json.loads(out)
        assert result["imported"] == 2
        assert result["skipped"] == 0
        assert result["errors"] == 0

        # Verify original_id is set in metadata
        imported = list_memories(storage_b)
        assert len(imported) == 2
        for rec in imported:
            assert "original_id" in rec["metadata"]

    def test_skip_exact_id_match(self, storage_a, export_file):
        """Import back into same project — all skipped by exact ID."""
        remember(storage_a, "existing", "Context")

        run_wt(storage_a, "export", "--output", export_file)
        out, rc = run_wt(storage_a, "import", export_file)
        assert rc == 0

        result = json.loads(out)
        assert result["imported"] == 0
        assert result["skipped"] == 1

        # No duplicates
        assert len(list_memories(storage_a)) == 1

    def test_skip_by_original_id_match(self, storage_a, storage_b, export_file):
        """Re-import same file — skip via original_id in target metadata."""
        remember(storage_a, "the memory", "Decision")

        run_wt(storage_a, "export", "--output", export_file)

        # First import: creates records with original_id in metadata
        run_wt(storage_b, "import", export_file)
        assert len(list_memories(storage_b)) == 1

        # Second import: should skip because original_id already known
        out, rc = run_wt(storage_b, "import", export_file)
        result = json.loads(out)
        assert result["imported"] == 0
        assert result["skipped"] == 1

        # Still just 1 record
        assert len(list_memories(storage_b)) == 1

    def test_skip_reverse_import(self, storage_a, storage_b, tmp_path):
        """incoming.metadata.original_id matches target record ID → skip."""
        # A has a record
        remember(storage_a, "original from A", "Decision")
        a_records = list_memories(storage_a)
        assert len(a_records) == 1
        a_id = a_records[0]["id"]

        # Export A → import into B
        export_ab = str(tmp_path / "a_to_b.json")
        run_wt(storage_a, "export", "--output", export_ab)
        run_wt(storage_b, "import", export_ab)

        # B now has the record with metadata.original_id = a_id
        b_records = list_memories(storage_b)
        assert len(b_records) == 1
        assert b_records[0]["metadata"]["original_id"] == a_id

        # Export B → try to import back into A
        export_ba = str(tmp_path / "b_to_a.json")
        run_wt(storage_b, "export", "--output", export_ba)
        out, rc = run_wt(storage_a, "import", export_ba)

        result = json.loads(out)
        assert result["imported"] == 0
        assert result["skipped"] == 1

        # A still has exactly 1 record
        assert len(list_memories(storage_a)) == 1

    def test_skip_double_import_original_id(self, storage_a, storage_b, tmp_path):
        """incoming.metadata.original_id matches target.metadata.original_id → skip."""
        # Create a record on A
        remember(storage_a, "shared memory", "Learning")

        # Export A
        export_file = str(tmp_path / "from_a.json")
        run_wt(storage_a, "export", "--output", export_file)

        # Import into B (gets original_id)
        run_wt(storage_b, "import", export_file)

        # Create a third storage C, import from A there too
        storage_c = str(tmp_path / "storage_c")
        os.makedirs(storage_c)
        run_wt(storage_c, "import", export_file)

        # Export B → import into C
        # C already has the record (with original_id from A)
        # B's export has original_id from A in metadata
        export_bc = str(tmp_path / "b_to_c.json")
        run_wt(storage_b, "export", "--output", export_bc)
        out, rc = run_wt(storage_c, "import", export_bc)

        result = json.loads(out)
        assert result["imported"] == 0
        assert result["skipped"] == 1

        # C still just 1 record
        assert len(list_memories(storage_c)) == 1


# ── 3.9 Full roundtrip ────────────────────────────────────────────────


class TestRoundtrip:
    def test_roundtrip_a_b_a(self, storage_a, storage_b, tmp_path):
        """A(3) → export → B import → B add 2 → export → A import → A has 5."""
        # A starts with 3 memories
        remember(storage_a, "A memory 1", "Decision", ["a"])
        remember(storage_a, "A memory 2", "Learning", ["a"])
        remember(storage_a, "A memory 3", "Context", ["a"])
        assert len(list_memories(storage_a)) == 3

        # A → export → B import
        export_ab = str(tmp_path / "a_to_b.json")
        run_wt(storage_a, "export", "--output", export_ab)
        out, _ = run_wt(storage_b, "import", export_ab)
        assert json.loads(out)["imported"] == 3
        assert len(list_memories(storage_b)) == 3

        # B adds 2 more memories
        remember(storage_b, "B memory 1", "Decision", ["b"])
        remember(storage_b, "B memory 2", "Learning", ["b"])
        assert len(list_memories(storage_b)) == 5

        # B → export → A import
        export_ba = str(tmp_path / "b_to_a.json")
        run_wt(storage_b, "export", "--output", export_ba)
        out, _ = run_wt(storage_a, "import", export_ba)

        result = json.loads(out)
        assert result["imported"] == 2  # only B's new ones
        assert result["skipped"] == 3   # A's original 3

        # A now has exactly 5, no duplicates
        a_final = list_memories(storage_a)
        assert len(a_final) == 5

        # Verify all content is present
        contents = {r["content"] for r in a_final}
        assert "A memory 1" in contents
        assert "A memory 2" in contents
        assert "A memory 3" in contents
        assert "B memory 1" in contents
        assert "B memory 2" in contents


# ── 3.10 Mixed import ─────────────────────────────────────────────────


class TestMixed:
    def test_import_mixed(self, storage_a, storage_b, export_file):
        """Import file with some new, some duplicate records."""
        # A has 2 records
        remember(storage_a, "shared memory", "Decision")
        remember(storage_a, "A only memory", "Learning")

        # B has 1 record (the shared one, imported from A)
        run_wt(storage_a, "export", "--output", export_file)
        # Manually pick just the first record for B
        data = json.loads(open(export_file).read())
        data["records"] = data["records"][:1]
        data["count"] = 1
        with open(export_file, "w") as f:
            json.dump(data, f)
        run_wt(storage_b, "import", export_file)

        # B adds its own
        remember(storage_b, "B unique memory", "Context")
        assert len(list_memories(storage_b)) == 2

        # Now export B and import into A
        export_ba = export_file + ".ba"
        run_wt(storage_b, "export", "--output", export_ba)
        out, rc = run_wt(storage_a, "import", export_ba)

        result = json.loads(out)
        assert result["imported"] == 1   # B unique
        assert result["skipped"] == 1    # shared (already in A via original_id)
        assert result["errors"] == 0


# ── 3.11 Dry-run ──────────────────────────────────────────────────────


class TestDryRun:
    def test_dry_run_no_writes(self, storage_a, storage_b, export_file):
        """Dry-run reports counts but writes nothing."""
        remember(storage_a, "dry run test", "Decision")
        run_wt(storage_a, "export", "--output", export_file)

        out, rc = run_wt(storage_b, "import", export_file, "--dry-run")
        assert rc == 0

        result = json.loads(out)
        assert result["dry_run"] is True
        assert result["would_import"] == 1
        assert result["would_skip"] == 0

        # Nothing actually written
        assert len(list_memories(storage_b)) == 0


# ── 3.12 Invalid file handling ────────────────────────────────────────


class TestInvalidFile:
    def test_invalid_json(self, storage_a, tmp_path):
        """Non-JSON file returns error."""
        bad = str(tmp_path / "bad.json")
        with open(bad, "w") as f:
            f.write("not json at all")

        out, rc = run_wt(storage_a, "import", bad)
        assert rc != 0
        result = json.loads(out)
        assert "error" in result
        assert "Invalid JSON" in result["error"]

    def test_wrong_version(self, storage_a, tmp_path):
        """Unknown version returns error."""
        bad = str(tmp_path / "v99.json")
        with open(bad, "w") as f:
            json.dump({"version": 99, "format": "set-memory-export", "records": []}, f)

        out, rc = run_wt(storage_a, "import", bad)
        assert rc != 0
        result = json.loads(out)
        assert "error" in result
        assert "Unsupported version" in result["error"]

    def test_missing_format(self, storage_a, tmp_path):
        """Missing format field returns error."""
        bad = str(tmp_path / "no-format.json")
        with open(bad, "w") as f:
            json.dump({"version": 1, "records": []}, f)

        out, rc = run_wt(storage_a, "import", bad)
        assert rc != 0
        result = json.loads(out)
        assert "error" in result

    def test_file_not_found(self, storage_a):
        """Non-existent file returns error."""
        _, rc = run_wt(storage_a, "import", "/tmp/does-not-exist-xyz.json")
        assert rc != 0
