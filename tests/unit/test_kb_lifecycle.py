"""The lifecycle: refresh-on-search, the writer lock, snapshot search,
reindex gates, worktree seeding — the behaviors every surface inherits."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest_kb import git, make_repo, write
from set_kb.config import CONFIG_REL
from set_kb.lifecycle import RefreshLock, load_project, refresh, search_project


def project_for(tmp_path, name="repo", config=None, populate=None):
    root = make_repo(tmp_path, name)
    if populate:
        populate(root)
    if config is not None:
        write(root / CONFIG_REL, json.dumps(config, ensure_ascii=False))
    return load_project(root)


def hit_paths(result):
    return sorted({h.path for h in result.hits})


BODY = "\n\n" + "word " * 30 + "\n"


def test_new_note_is_found_immediately(tmp_path):
    """AC: WHEN a note is saved and searched right after THEN it is on the
    page — no separate index command exists on this path."""
    project = project_for(tmp_path)
    r1 = search_project(project, "freshnote")
    assert hit_paths(r1) == []
    write(Path(project.root) / "notes" / "fresh.md", "# Fresh\n\nfreshnote content" + BODY)
    r2 = search_project(project, "freshnote")
    assert hit_paths(r2) == ["notes/fresh.md"]
    assert r2.refreshed is True


def test_no_reindex_skips_the_refresh(tmp_path):
    """AC: WHEN no-reindex is set THEN the index is not modified — the new
    note stays off the page and the refresh note says why."""
    project = project_for(tmp_path)
    search_project(project, "word")
    write(Path(project.root) / "notes" / "later.md", "# Later\n\nlaterword content" + BODY)
    r = search_project(project, "laterword", no_reindex=True)
    assert hit_paths(r) == [], "the index was served as it stands"
    assert r.no_reindex is True and any("--no-reindex" in n for n in r.notes)
    r2 = search_project(project, "laterword")
    assert hit_paths(r2) == ["notes/later.md"], "the next ordinary search refreshes"


def test_channel_rules_edited_reclassify_unchanged_files(tmp_path):
    """AC: WHEN channel rules change THEN the next search rebuilds the rows
    with the new classification instead of keeping old labels."""
    project = project_for(tmp_path, config={"channels": []})
    write(Path(project.root) / "clients" / "mail.md", "# Client mail\n\nclientword" + BODY)
    search_project(project, "clientword")
    r1 = search_project(project, "clientword", no_reindex=True)
    assert r1.hits[0].channel is None

    write(
        Path(project.root) / CONFIG_REL,
        json.dumps({"channels": [{"channel": "client", "roots": [""], "include": ["clients/**"]}]}),
    )
    project.config = load_project(project.root).config  # the CLI reloads per run
    r2 = search_project(project, "clientword")
    assert r2.refreshed is True, "the corpus-config hash gate forces the re-chunk"
    assert r2.hits[0].channel == "client", "unchanged file, new classification"


def test_two_searches_do_not_race(tmp_path):
    """AC: WHEN two searches start together THEN one refreshes, the other uses
    the snapshot with a note, neither fails."""
    project = project_for(tmp_path)
    write(Path(project.root) / "note.md", "# Note\n\nsharedword" + BODY)
    search_project(project, "sharedword")

    with RefreshLock(project.lock_path) as held:
        assert held.acquired
        r = search_project(project, "sharedword")
        assert r.snapshot is True and r.refreshed is False
        assert any("snapshot" in n for n in r.notes), "the page says it did not refresh"
        assert hit_paths(r) == ["note.md"], "the snapshot still answers"
    r2 = search_project(project, "sharedword")
    assert r2.refreshed is True and r2.snapshot is False


def test_interrupted_first_build_leaves_no_index(tmp_path, monkeypatch):
    """AC: WHEN the first build is killed THEN no index exists at the final
    path and the next search rebuilds."""
    project = project_for(tmp_path)
    write(Path(project.root) / "note.md", "# Note\n\nword" + BODY)

    from set_kb import indexer as indexer_mod

    def boom(store, source, opts):
        raise RuntimeError("simulated kill mid-build")

    monkeypatch.setattr(indexer_mod, "index_source", boom)
    with pytest.raises(RuntimeError):
        refresh(project)
    monkeypatch.undo()
    import os

    assert not os.path.exists(project.db_path), "the final path never appears on a failed first build"
    r = search_project(project, "word")
    assert hit_paths(r) == ["note.md"], "the next search rebuilds cleanly"


def test_worktree_first_search_is_seeded(tmp_path):
    """AC: WHEN a new worktree searches first THEN its index is seeded from
    the main checkout and only files that differ are re-indexed."""
    project = project_for(tmp_path)
    write(Path(project.root) / "keep.md", "# Keep\n\nsharedword" + BODY)
    write(Path(project.root) / "change.md", "# Change\n\nsharedword" + BODY)
    search_project(project, "sharedword")  # the main checkout now has an index

    wt = tmp_path / "wt"
    git(project.root, "add", ".")
    git(project.root, "commit", "-q", "-m", "corpus")
    git(project.root, "worktree", "add", "-q", "-b", "feat", str(wt))
    write(wt / "change.md", "# Change\n\nchangedword" + BODY)  # one file differs

    wt_project = load_project(wt)
    stats = refresh(wt_project).stats
    assert wt_project.seeded is True, "the index was copied, not rebuilt"
    assert stats["changed"] == 1, "only the file that differs was re-indexed"
    assert stats["scanned"] >= 2
    # the worktree's own edit is searchable right away
    r2 = search_project(wt_project, "changedword")
    assert hit_paths(r2) == ["change.md"]


def test_scope_filter_at_project_level(tmp_path):
    project = project_for(
        tmp_path,
        config={"scopes": [{"name": "client", "pattern": "clients/{scope}/**"}]},
    )
    write(Path(project.root) / "clients" / "alfa" / "a.md", "# Alfa\n\nscopedword" + BODY)
    write(Path(project.root) / "clients" / "beta" / "b.md", "# Beta\n\nscopedword" + BODY)
    r = search_project(project, "scopedword", scope="client=alfa")
    assert hit_paths(r) == ["clients/alfa/a.md"], "no other client's file on the page"
    assert all(h.scope == "client=alfa" for h in r.hits)


def test_lane_disabled_for_one_search(tmp_path):
    project = project_for(
        tmp_path,
        config={
            "channels": [{"channel": "client", "roots": [""], "include": ["clients/**"]}],
            "ranking": {"laneChannels": ["client"], "laneQuota": 0.5},
        },
    )
    write(Path(project.root) / "clients" / "mail.md", "# Client mail\n\nlaneword" + BODY)
    write(Path(project.root) / "docs" / "plan.md", "# Planning\n\nlaneword planlane" + BODY)
    on = search_project(project, "laneword")
    assert on.hits, "the lane is in force by default"
    off = search_project(project, "laneword", lane=False)
    assert [h.score for h in off.hits] == sorted(h.score for h in off.hits), "pure score order"


def test_machine_layer_is_honored(tmp_path, tmp_path_factory):
    machine = tmp_path_factory.mktemp("machine") / "kb.json"
    machine.write_text(json.dumps({"exclude": ["machine-hidden/**"]}), encoding="utf-8")
    root = make_repo(tmp_path)
    write(root / "machine-hidden" / "x.md", "# hidden machine-word" + BODY)
    write(root / "keep.md", "# keep machine-word" + BODY)
    project = load_project(root, machine_path=machine)
    r = search_project(project, "machine-word")
    assert hit_paths(r) == ["keep.md"]
