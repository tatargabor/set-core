"""The `set-kb` command line: the single implementation surface and the
contracts the spec pins on it — repo-root resolution from any subdirectory,
the non-zero exit outside a repository, the zero-hit page that names its
query, the versioned JSON field set, and `get` accepting a hit's path
unchanged."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest_kb import make_repo, write

BIN = Path(__file__).resolve().parents[2] / "bin" / "set-kb"

BODY = "\n\n" + "word " * 30 + "\n"


def run_cli(args, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BIN), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )


def cli_project(tmp_path, name="repo") -> Path:
    """A throwaway project with the `.set/` ignore entry a real deploy writes."""
    return make_repo(tmp_path, name)


def note(root: Path, rel: str, title: str, marker: str) -> Path:
    return write(root / rel, f"# {title}\n\n{marker} content" + BODY)


# ── resolution and exit codes ────────────────────────────────────────────────


def test_search_outside_a_repository(tmp_path):
    """AC: WHEN set-kb runs outside a repository THEN it exits non-zero saying
    no project was found."""
    plain = tmp_path / "plain"
    plain.mkdir()
    r = run_cli(["search", "anything"], cwd=plain)
    assert r.returncode != 0
    assert "no project" in r.stderr


def test_search_from_a_subdirectory_uses_the_project_index(tmp_path):
    """AC: WHEN search runs in a subdirectory THEN it searches the project
    index and prints root-relative paths."""
    root = cli_project(tmp_path)
    note(root, "docs/deep/note.md", "Deep note", "buriedword")
    (root / "docs" / "deep").mkdir(parents=True, exist_ok=True)
    r = run_cli(["search", "buriedword"], cwd=root / "docs" / "deep")
    assert r.returncode == 0
    assert "docs/deep/note.md" in r.stdout, "the path is relative to the REPOSITORY root"


def test_sources_from_a_subdirectory_resolves_the_same_root(tmp_path):
    root = cli_project(tmp_path)
    note(root, "a.md", "A", "markera")
    r1 = run_cli(["sources", "--json"], cwd=root)
    sub = root / "sub"
    sub.mkdir()
    r2 = run_cli(["sources", "--json"], cwd=sub)
    assert json.loads(r1.stdout)["root"] == json.loads(r2.stdout)["root"]


# ── the text page ────────────────────────────────────────────────────────────


def test_zero_hit_page_names_the_query_and_the_exclusions(tmp_path):
    """AC: WHEN there are zero hits THEN the page prints the exact query and
    the exclusions in force."""
    root = cli_project(tmp_path)
    note(root, "note.md", "Note", "someword")
    r = run_cli(["search", "xyzzyplugh qwertyfoo"], cwd=root)
    assert r.returncode == 0, "zero hits is an answer, not a failure"
    assert 'no hits for "xyzzyplugh qwertyfoo"' in r.stdout
    assert "indexed corpus excludes:" in r.stdout
    assert "paths relative to:" in r.stdout
    assert "index:" in r.stdout


def test_results_beyond_the_limit_are_stated(tmp_path):
    """AC: WHEN more sources match than the limit THEN the page states how
    many more."""
    root = cli_project(tmp_path)
    for i in range(10):
        note(root, f"n{i}.md", f"Note {i}", f"sharedword variant{i}")
    r = run_cli(["search", "sharedword", "--limit", "8"], cwd=root)
    assert r.returncode == 0
    assert "showing 8 of 10 matching sources — 2 more match" in r.stdout


# ── the JSON contract ────────────────────────────────────────────────────────


def test_json_contract_field_set(tmp_path):
    """The stable contract: version, the footer facts as fields, and per hit
    the repo-relative path, heading path, LEAF heading, snippet, score,
    channel, scope, further-section count and duplicate count."""
    import pytest

    from set_kb.lang_hu import hungarian_pack  # noqa: F401 — "hu" resolves in config

    root = cli_project(tmp_path)
    write(
        root / "set" / "knowledge" / "kb.json",
        json.dumps({"channels": [{"channel": "notes", "roots": [""], "include": ["notes/**"]}], "ranking": {"laneChannels": ["notes"], "laneQuota": 0.5}}),
    )
    note(root, "notes/team.md", "Team note", "jsonword")
    r = run_cli(["search", "jsonword", "--json"], cwd=root)
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["version"] == 1
    for field in ("hits", "total", "hasMore", "exclusions", "refreshed", "notes", "root", "query"):
        assert field in d, f"the contract carries {field}"
    hit = d["hits"][0]
    for field in ("path", "headingPath", "heading", "snippet", "score", "channel", "scope", "suppressedSections", "duplicateCount", "root"):
        assert field in hit, f"a hit carries {field}"
    assert hit["path"] == "notes/team.md", "the hit path is repository-relative"
    assert hit["channel"] == "notes"
    assert hit["heading"] == "Team note"


def test_a_script_consumes_the_hits_then_get(tmp_path):
    """AC: WHEN a script reads hits[0].path THEN set-kb get accepts it
    unchanged."""
    root = cli_project(tmp_path)
    note(root, "docs/handbook.md", "Handbook", "pipeline")
    r = run_cli(["search", "pipeline", "--json"], cwd=root)
    hit = json.loads(r.stdout)["hits"][0]
    g = run_cli(["get", hit["path"]], cwd=root)
    assert g.returncode == 0
    assert "# Handbook" in g.stdout
    sec = run_cli(["get", hit["path"], "--section", hit["headingPath"]], cwd=root)
    assert sec.returncode == 0
    assert "pipeline content" in sec.stdout


def test_get_json_section_and_missing(tmp_path):
    root = cli_project(tmp_path)
    write(root / "f.md", "# T\n\nintro\n\n## Alpha\n\nalpha body\n" + BODY + "\n## Beta\n\nbeta body\n" + BODY)
    run_cli(["search", "intro"], cwd=root)  # the index must exist before get
    r = run_cli(["get", "f.md", "--section", "Alpha", "--json"], cwd=root)
    d = json.loads(r.stdout)
    assert d["found"] is True and "alpha body" in d["body"] and "beta body" not in d["body"]
    r2 = run_cli(["get", "f.md", "--section", "Nope", "--json"], cwd=root)
    assert r2.returncode == 1
    assert json.loads(r2.stdout)["kind"] == "missing"


def test_ambiguous_leaf_lists_full_paths_prints_no_section(tmp_path):
    """AC: WHEN a leaf heading is ambiguous THEN both full paths are listed
    and no section is printed."""
    root = cli_project(tmp_path)
    write(root / "ambig.md", "# T\n\nintro\n\n## Decision\n\nfirst one\n" + BODY + "\n## Other\n\nother section\n" + BODY + "\n### Decision\n\nsecond one\n" + BODY)
    run_cli(["search", "intro"], cwd=root)  # the index must exist before get
    r = run_cli(["get", "ambig.md", "--section", "Decision"], cwd=root)
    assert r.returncode == 1
    assert "first one" not in r.stdout + r.stderr, "neither section is printed"
    assert "T > Decision" in r.stderr and "T > Other > Decision" in r.stderr


# ── sources ──────────────────────────────────────────────────────────────────


def test_sources_shows_the_configured_descriptions(tmp_path):
    """AC: WHEN set-kb sources runs THEN each root and channel shows the
    description from the config."""
    root = cli_project(tmp_path)
    write(
        root / "set" / "knowledge" / "kb.json",
        json.dumps(
            {
                "sources": [{"ref": "", "about": "the whole repository"}],
                "channels": [{"channel": "client", "roots": [""], "include": ["clients/**"], "about": "the client's own words"}],
            }
        ),
    )
    write(root / "clients" / "mail.md", "# Mail\n\nclientword" + BODY)
    r = run_cli(["sources"], cwd=root)
    assert "the whole repository" in r.stdout
    assert "the client's own words" in r.stdout
    r2 = run_cli(["sources", "--json"], cwd=root)
    d = json.loads(r2.stdout)
    assert d["roots"][0]["about"] == "the whole repository"
    assert d["channels"][0]["about"] == "the client's own words"


# ── index ────────────────────────────────────────────────────────────────────


def test_index_command_reports_the_refresh(tmp_path):
    root = cli_project(tmp_path)
    note(root, "a.md", "A", "marker")
    r = run_cli(["index", "--json"], cwd=root)
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["command"] == "index" and d["version"] == 1
    assert d["counts"]["files"] == 1


def test_no_reindex_serves_the_index_as_it_stands(tmp_path):
    """AC: measurement run without refresh — the page says the index was not
    refreshed."""
    root = cli_project(tmp_path)
    note(root, "a.md", "A", "markerword")
    r = run_cli(["search", "markerword"], cwd=root)  # builds the index
    assert r.returncode == 0
    note(root, "later.md", "Later", "laterword")
    r2 = run_cli(["search", "laterword", "--no-reindex"], cwd=root)
    assert r2.returncode == 0
    assert "not refreshed (--no-reindex)" in r2.stdout
    assert "no hits" in r2.stdout, "the new note is not in the index as it stands"
    r3 = run_cli(["search", "laterword"], cwd=root)
    assert "later.md" in r3.stdout
