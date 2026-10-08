"""Findability: recordings discovered by stem or date-and-part prefix, hidden
ones naming their exclusion rule, title queries landing in the top k, and the
project's own globs checked the same way."""

from __future__ import annotations

import json
import os
from pathlib import Path

from conftest_kb import make_repo, write
from set_kb.findability import discover, recording_key
from set_kb.lifecycle import load_project

BODY = "\n\n" + "word " * 30 + "\n"

TRANSCRIPT = "# Őszi sprint tervező megbeszélés\n\nA megbeszélés a sprint ütemezéséről szólt." + BODY


def make_project(tmp_path, config=None):
    root = make_repo(tmp_path, "findproj")
    if config is not None:
        write(root / "set" / "knowledge" / "kb.json", json.dumps(config))
    return load_project(root)


def test_recording_key_matches_date_and_part_prefix():
    """Same stem always matches; the date-and-part prefix matches across the
    `-raw-partN` decoration the recorders add."""
    assert recording_key("2026-09-12-tervezes-part1") == "2026-09-12-tervezes"
    assert recording_key("2026-09-12-tervezes-raw-part1") == "2026-09-12-tervezes"
    assert recording_key("2026-09-12-tervezes") == "2026-09-12-tervezes"
    assert recording_key("2026-09-12-tervezes-part2") == "2026-09-12-tervezes"
    assert recording_key("kickoff") is None, "no date prefix → stem matching only"
    assert recording_key("2026-09-12") == "2026-09-12"


def test_discovery_finds_the_pair_and_the_prefix_pair(tmp_path):
    project = make_project(tmp_path)
    write(Path(project.root) / "meetings" / "2026-09-12-tervezes-part1.md", TRANSCRIPT)
    write(Path(project.root) / "meetings" / "2026-09-12-tervezes-part1.jsonl", "{}\n")
    write(Path(project.root) / "meetings" / "2026-09-30-kickoff.md", "# Kickoff\n" + BODY)
    write(Path(project.root) / "meetings" / "2026-09-30-kickoff-raw-part1.jsonl", "{}\n")
    cands = discover(project.root, project.config)
    paths = {c.path for c in cands}
    assert "meetings/2026-09-12-tervezes-part1.md" in paths
    assert "meetings/2026-09-30-kickoff.md" in paths, "the date-and-part prefix identifies the pair"
    assert not any(".jsonl" in c.path for c in cands), "the recording itself is never a candidate"


def test_hidden_recording_names_the_rule_and_fails(tmp_path):
    """AC: WHEN a readable transcript sits next to its recording inside a
    folder an exclusion rule matches THEN findability reports not indexed,
    names the rule, and (via the CLI) exits non-zero."""
    project = make_project(tmp_path, config={"exclude": ["meetings/**"]})
    write(Path(project.root) / "meetings" / "2026-09-12-tervezes-part1.md", TRANSCRIPT)
    write(Path(project.root) / "meetings" / "2026-09-12-tervezes-part1.jsonl", "{}\n")
    from set_kb.findability import run_findability

    report = run_findability(project)
    assert not report.ok
    r = report.level1_missed[0]
    assert r.reason == "meetings/**", "the miss names the rule that hid it"


def test_indexed_transcript_is_retrievable_by_title(tmp_path):
    """AC: WHEN a transcript titled with its meeting topic is indexed THEN the
    title query returns it within the top 10."""
    project = make_project(tmp_path)
    write(Path(project.root) / "meetings" / "2026-09-12-tervezes-part1.md", TRANSCRIPT)
    write(Path(project.root) / "meetings" / "2026-09-12-tervezes-part1.jsonl", "{}\n")
    from set_kb.findability import run_findability

    report = run_findability(project)
    assert report.ok
    r = report.results[0]
    assert r.indexed and r.rank is not None and r.rank <= 10
    assert r.query, "the query came from the title, not the path"


def test_findability_globs_are_checked_like_recordings(tmp_path):
    """AC: WHEN a project lists globs THEN those notes are checked the same
    way as recordings — including a miss on a glob no rule covers."""
    project = make_project(tmp_path, config={"findability": {"globs": ["docs/decisions/**/*.md"]}})
    write(Path(project.root) / "docs" / "decisions" / "d1.md", "# Engine adoption decision\n\nhow we chose" + BODY)
    write(Path(project.root) / "docs" / "decisions" / "d2.md", "# Cache invalidation decision\n\ncache" + BODY)
    from set_kb.findability import run_findability

    report = run_findability(project)
    assert report.ok
    kinds = {r.candidate.path: r.candidate.kind for r in report.results}
    assert kinds["docs/decisions/d1.md"] == "glob"
    assert all(r.rank is not None for r in report.results)


def test_title_query_miss_is_listed(tmp_path):
    """A level-2 miss does not flip the exit (only level-1 does) but is
    listed with its query."""
    project = make_project(tmp_path, config={"findability": {"globs": ["notes/**"]}})
    write(Path(project.root) / "notes" / "a.md", "# Completely unique zephyrquartz topic\n" + BODY)
    write(Path(project.root) / "notes" / "b.md", "no heading at all, only body text" + BODY)
    from set_kb.findability import run_findability

    report = run_findability(project)
    assert report.ok, "both are indexed — level 1 passes"
    by_path = {r.candidate.path: r for r in report.results}
    assert by_path["notes/b.md"].note, "the heading-less note says why level 2 skipped it"
    a = by_path["notes/a.md"]
    assert a.query and a.rank is not None, "a title like nothing else in the corpus must rank first"


def test_cli_findability_exit_codes(tmp_path):
    """The command exits non-zero exactly on level-1 misses."""
    from test_kb_cli import run_cli

    root = make_repo(tmp_path, "cliexit")
    write(root / "meetings" / "2026-09-12-tervezes-part1.md", TRANSCRIPT)
    write(root / "meetings" / "2026-09-12-tervezes-part1.jsonl", "{}\n")
    ok = run_cli(["findability", "--json"], cwd=root)
    assert ok.returncode == 0
    d = json.loads(ok.stdout)
    assert d["ok"] is True and d["level1"]["missed"] == 0
    write(root / "set" / "knowledge" / "kb.json", json.dumps({"exclude": ["meetings/**"]}))
    bad = run_cli(["findability", "--json"], cwd=root)
    assert bad.returncode == 1
    d2 = json.loads(bad.stdout)
    assert d2["ok"] is False
    miss = [c for c in d2["candidates"] if not c["indexed"]][0]
    assert miss["reason"] == "meetings/**"
