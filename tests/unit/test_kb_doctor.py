"""`set-kb doctor`: blocking vs informational checks, and the per-rule
exclusion counts that make a silently shrunken corpus visible."""

from __future__ import annotations

import json
import os

from conftest_kb import make_repo, write

from test_kb_cli import run_cli

BODY = "\n\n" + "word " * 30 + "\n"


def healthy_project(tmp_path) -> str:
    root = make_repo(tmp_path, "docproj")
    write(root / "note.md", "# Note\n\nhealthword" + BODY)
    return str(root)


def test_healthy_project_exits_zero_with_counts(tmp_path):
    """AC: WHEN the project is healthy THEN doctor exits zero and prints the
    counts per root, channel and exclusion rule."""
    root = healthy_project(tmp_path)
    run_cli(["search", "healthword"], cwd=root)  # build the index first
    r = run_cli(["doctor", "--json"], cwd=root)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True
    by_name = {c["name"]: c for c in d["checks"]}
    for name in ("project", "python", "runtime", "config", "ignore", "index"):
        assert by_name[name]["status"] == "ok", name
    assert d["roots"] and d["roots"][0]["files"] == 1
    assert d["exclusions"] == [] or all("files" in e for e in d["exclusions"])


def test_excluded_share_is_visible_with_counts_per_rule(tmp_path):
    """AC: WHEN an exclusion rule removes files from the corpus THEN doctor
    prints that rule with its count — a shrunken corpus must not read as a
    full one (the measured W2 case: build output and node_modules markdown)."""
    root = healthy_project(tmp_path)
    for rel in ("node_modules/pkg/readme.md", "dist/report.md", "keep1.md", "keep2.md"):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        write(__import__("pathlib").Path(p), "# x\n")
    r = run_cli(["doctor", "--json"], cwd=root)
    d = json.loads(r.stdout)
    rules = {e["rule"]: e["files"] for e in d["exclusions"]}
    assert rules.get("node_modules/") == 1
    assert rules.get("dist/") == 1
    text = run_cli(["doctor"], cwd=root).stdout
    assert "excluded by node_modules/: 1 file(s)" in text


def test_config_error_is_blocking_and_names_the_key(tmp_path):
    """A config that fails validation BLOCKS search — doctor exits non-zero
    and carries the offending key path."""
    root = make_repo(tmp_path, "badcfg")
    write(root / "note.md", "# Note\n\nw" + BODY)
    write(root / "set" / "knowledge" / "kb.json", json.dumps({"channels": [{"channel": "x", "include": ["a/**"]}]}))
    r = run_cli(["doctor", "--json"], cwd=root)
    assert r.returncode == 1
    d = json.loads(r.stdout)
    assert d["ok"] is False
    blocked = [c for c in d["checks"] if c["status"] == "blocked"]
    assert any("config.channels[0]" in c["detail"] for c in blocked)


def test_unignored_index_path_is_blocking(tmp_path):
    """The index must never be writable where git could commit it — a missing
    `.set/` ignore entry blocks, naming the path."""
    root = make_repo(tmp_path, "noignore", gitignored=False)
    write(root / "note.md", "# Note\n\nw" + BODY)
    r = run_cli(["doctor"], cwd=root)
    assert r.returncode == 1
    assert ".set/kb/index.db" in r.stdout


def test_missing_index_is_a_warning_not_a_block(tmp_path):
    """A missing index does not BLOCK search — the first search builds it.
    Doctor says so and still exits zero."""
    root = make_repo(tmp_path, "empty")
    write(root / "note.md", "# Note\n\nw" + BODY)
    r = run_cli(["doctor", "--json"], cwd=root)
    assert r.returncode == 0
    d = json.loads(r.stdout)
    by_name = {c["name"]: c for c in d["checks"]}
    assert by_name["index"]["status"] == "warn"
    assert "first search builds it" in by_name["index"]["detail"]
    assert d["index"]["present"] is False
