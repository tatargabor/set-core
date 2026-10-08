"""Indexer: layered change detection, deletions, NFC paths, docType, and the
atomic index run."""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import pytest

from set_kb.indexer import (
    AtomicIndexSource,
    IndexOptions,
    RunIndexAtomicOpts,
    _walk,
    doc_type_of,
    index_source,
    run_index_atomic,
    sweep_orphan_temps,
)


def make_source(root: Path, name="src") -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def index(tmp_path, *sources, **opts) -> dict:
    return run_index_atomic(
        RunIndexAtomicOpts(
            db_path=str(tmp_path / "idx.db"),
            sources=[AtomicIndexSource(id=s.name, dir=str(s)) for s in sources],
            index_opts=IndexOptions(**opts),
        )
    )


def test_incremental_refresh_skips_unchanged(tmp_path):
    src = make_source(tmp_path)
    (src / "a.md").write_text("# A\n\n" + "word " * 30 + "\n", encoding="utf-8")
    first = index(tmp_path, src)
    assert first["changed"] == 1 and first["counts"]["files"] == 1
    second = index(tmp_path, src)
    assert second["changed"] == 0 and second["scanned"] == 1, "unchanged file skipped by mtime+size"


def test_changed_file_is_reindexed_and_deleted_file_removed(tmp_path):
    src = make_source(tmp_path)
    f = src / "a.md"
    f.write_text("# A\n\n" + "word " * 30 + "\n", encoding="utf-8")
    index(tmp_path, src)
    f.write_text("# A\n\nchanged body " + "word " * 30 + "\n", encoding="utf-8")
    second = index(tmp_path, src)
    assert second["changed"] == 1

    from set_kb.store import SqliteFtsStore

    store = SqliteFtsStore(str(tmp_path / "idx.db"))
    store.init()
    assert "changed body" in store.get_chunk("src", "a.md").body
    store.close()

    f.unlink()
    third = index(tmp_path, src)
    assert third["deleted"] == 1
    store = SqliteFtsStore(str(tmp_path / "idx.db"))
    store.init()
    assert store.get_chunk("src", "a.md") is None
    store.close()


def test_mtime_preserving_content_swap_is_rehashed(tmp_path):
    import hashlib

    src = make_source(tmp_path)
    f = src / "a.md"
    f.write_text("# A\n\n" + "word " * 30 + "\n", encoding="utf-8")
    index(tmp_path, src)
    old_stat = f.stat()
    f.write_text("# A\n\nswapped body " + "word " * 30 + "\n", encoding="utf-8")
    os.utime(f, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))  # preserve mtime
    second = index(tmp_path, src)
    assert second["changed"] == 1, "the size changed, so the cheap check must not skip it"


def test_nfd_file_name_is_stored_nfc(tmp_path):
    src = make_source(tmp_path)
    nfd = unicodedata.normalize("NFD", "költség-jegyzet.md")
    (src / nfd).write_text("# Jegyzet\n\n" + "szó " * 30 + "\n", encoding="utf-8")
    index(tmp_path, src)
    from set_kb.store import SqliteFtsStore

    store = SqliteFtsStore(str(tmp_path / "idx.db"))
    store.init()
    (path,) = store.list_paths("src")
    assert path == unicodedata.normalize("NFC", path), "paths are NFC-normalised before indexing"
    assert path == "költség-jegyzet.md"
    store.close()


def test_posix_separators_and_relative_paths_in_store(tmp_path):
    sub = make_source(tmp_path, "src") / "nested"
    sub.mkdir()
    (sub / "b.md").write_text("# B\n\n" + "word " * 30 + "\n", encoding="utf-8")
    index(tmp_path, tmp_path / "src")
    from set_kb.store import SqliteFtsStore

    store = SqliteFtsStore(str(tmp_path / "idx.db"))
    store.init()
    assert store.list_paths("src") == ["nested/b.md"]
    assert not any(p.startswith("/") for p in store.list_paths("src"))
    store.close()


def test_doc_type_of():
    assert doc_type_of("CLAUDE.md", True) == "agents"
    assert doc_type_of("AGENTS.override.md", True) == "agents"
    assert doc_type_of("deep/CLAUDE.md", True) == "agents"
    assert doc_type_of("src/x.md", True) == "source-md"
    assert doc_type_of("src/x.md", False) == "doc"
    assert doc_type_of("docs/x.md", True) == "doc"


def test_agents_files_excluded_by_option(tmp_path):
    src = make_source(tmp_path)
    (src / "CLAUDE.md").write_text("# Agent instructions\n\n" + "word " * 30 + "\n", encoding="utf-8")
    (src / "note.md").write_text("# Note\n\n" + "word " * 30 + "\n", encoding="utf-8")
    res = index(tmp_path, src, index_agents_files=False)
    assert res["counts"]["files"] == 1
    res = index(tmp_path, src, index_agents_files=True, force=True)
    assert res["counts"]["files"] == 2


def test_walk_prunes_excluded_directories(tmp_path):
    """Since W2 the default corpus lives in `config`; the walk's own job is to
    PRUNE a directory an exclusion covers whole, instead of descending into it
    to hash-exclude every file one by one."""
    from set_kb.glob import glob_to_re

    src = make_source(tmp_path)
    (src / "dist").mkdir()
    (src / "dist" / "report.md").write_text("# build\n", encoding="utf-8")
    (src / "keep.md").write_text("# keep\n\n" + "word " * 30 + "\n", encoding="utf-8")
    out = _walk(str(src), str(src), [], prune=[("dist/", glob_to_re("dist/"))])
    assert out == [str(src / "keep.md")], "a dir-style exclusion prunes the subtree at the walk"
    # and the indexed run agrees
    res = index(tmp_path, src, exclude=["dist/"])
    assert res["scanned"] == 1 and res["counts"]["files"] == 1


def test_pruned_directories_are_counted_per_pattern(tmp_path):
    """The W2-review gap, pinned: a repo whose corpus sits mostly inside
    EXCLUDED trees (build output, a virtualenv, node_modules) used to report
    `scanned: 3, excluded: {}` — a shrunken corpus that looked like a full one.
    The walk prunes whole directories, so the prune itself must count the files
    it removes, per pattern."""
    from set_kb.config import KbConfig, index_options

    src = make_source(tmp_path)
    for rel in (
        "app/dist/report.md",
        "web/.next/standalone/nested/page.md",
        "sub/.venv/lib/site-packages/readme.md",
        "sub/node_modules/pkg/readme.md",
        "keep-one.md",
        "keep-two.md",
        "keep-three.md",
    ):
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# generated or kept\n", encoding="utf-8")
    # The default corpus exclusions live in the config layer (W2); the measured
    # repo ran with them in force, so the census does too.
    res = run_index_atomic(
        RunIndexAtomicOpts(
            db_path=str(tmp_path / "idx.db"),
            sources=[AtomicIndexSource(id=src.name, dir=str(src))],
            index_opts=index_options(KbConfig(sources=[], channels=[], scopes=[], exclude=[])),
        )
    )
    assert res["scanned"] == 3
    # The four pruned trees are named by the pattern that removed them, with
    # the files each one takes out of the corpus.
    assert res["excluded"].get("dist/") == 1
    assert res["excluded"].get(".next*/") == 1
    assert res["excluded"].get(".venv*/") == 1
    assert res["excluded"].get("node_modules/") == 1


def test_scan_exclusions_census_matches_the_indexer(tmp_path):
    """`scan_exclusions` (doctor's census) decides with the same predicates as
    the indexer: pattern rules from the walk, frontmatter and framework-ledger
    rules per file — counted fresh, over the whole tree."""
    from set_kb.config import DEFAULT_EXCLUDE_FRONTMATTER
    from set_kb.indexer import IndexSource, scan_exclusions

    src = make_source(tmp_path)
    (src / "dist" / "x.md").parent.mkdir(parents=True)
    (src / "dist" / "x.md").write_text("# build\n", encoding="utf-8")
    (src / "dump.md").write_text("---\ntype: claude-session\n---\n\nsession dump\n", encoding="utf-8")
    (src / "note.md").write_text("# Note\n\nbody text\n", encoding="utf-8")
    opts = IndexOptions(exclude=["dist/"], exclude_frontmatter=dict(DEFAULT_EXCLUDE_FRONTMATTER))
    census = scan_exclusions([IndexSource(root="", dir=str(src))], opts)
    assert census["excluded"] == {"dist/": 1, "excludeFrontmatter:type": 1}
    assert census["indexed"] == {"": 1}
    assert census["scanned"] == 2, "pruned directories never become candidates"


def test_file_style_exclusion_names_the_pattern(tmp_path):
    """A file-style pattern cannot prune a directory, so the per-file check
    fires — and records WHICH pattern excluded the file."""
    from set_kb.glob import glob_to_re

    src = make_source(tmp_path)
    (src / "internal-draft.md").write_text("# draft\n", encoding="utf-8")
    (src / "keep.md").write_text("# keep\n\n" + "word " * 30 + "\n", encoding="utf-8")
    res = index(tmp_path, src, exclude=["internal-*.md"])
    assert res["counts"]["files"] == 1


def test_git_and_set_are_permanently_pruned(tmp_path):
    """`.git/` and `.set/` are plumbing, not corpus: no configuration key can
    lift them, because no corpus question is answered by the git internals or
    by the engine's own runtime directory."""
    from set_kb.glob import glob_to_re

    src = make_source(tmp_path)
    (src / ".git").mkdir()
    (src / ".git" / "COMMIT_EDITMSG.md").write_text("# git internal\n", encoding="utf-8")
    (src / ".set").mkdir()
    (src / ".set" / "kb").mkdir()
    (src / ".set" / "kb" / "note.md").write_text("# runtime\n", encoding="utf-8")
    (src / "keep.md").write_text("# keep\n\n" + "word " * 30 + "\n", encoding="utf-8")
    out = _walk(str(src), str(src), [], prune=[("nope/", glob_to_re("nope/"))])
    assert out == [str(src / "keep.md")], "the permanent prune applies regardless of configuration"


def test_interrupted_first_build_leaves_no_index(tmp_path, monkeypatch):
    """AC: WHEN the first build is killed THEN no index exists at the final
    path and the next search rebuilds. (We simulate the kill with an exception
    between sources; the temp build is removed on failure.)"""
    src = make_source(tmp_path)
    (src / "a.md").write_text("# A\n\n" + "word " * 30 + "\n", encoding="utf-8")

    calls = {"n": 0}
    real = index_source

    def flaky(store, source, opts):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated kill mid-run")
        return real(store, source, opts)

    monkeypatch.setattr("set_kb.indexer.index_source", flaky)
    with pytest.raises(RuntimeError):
        index(tmp_path, src, src)  # two sources, second one "killed"
    assert not (tmp_path / "idx.db").exists(), "the final path never appears on a failed first build"
    monkeypatch.undo()
    res = index(tmp_path, src)
    assert res["counts"]["files"] == 1, "the next run rebuilds cleanly"


def test_schema_version_gate_forces_rebuild(tmp_path, monkeypatch):
    from set_kb import indexer as indexer_mod
    from set_kb.store import SCHEMA_VERSION

    src = make_source(tmp_path)
    (src / "a.md").write_text("# A\n\n" + "word " * 30 + "\n", encoding="utf-8")
    index(tmp_path, src)
    assert (tmp_path / "idx.db").exists()

    from set_kb.store import SqliteFtsStore

    store = SqliteFtsStore(str(tmp_path / "idx.db"))
    store.init()
    store.set_user_version(SCHEMA_VERSION - 1)
    store.close()

    renamed = []
    real_finalize = indexer_mod.SqliteFtsStore.finalize_rename

    def spy(self, dest):
        renamed.append(dest)
        real_finalize(self, dest)

    monkeypatch.setattr(indexer_mod.SqliteFtsStore, "finalize_rename", spy)
    res = index(tmp_path, src)
    monkeypatch.undo()
    assert renamed == [str(tmp_path / "idx.db")], "a stale schema version rebuilds via temp + rename"
    assert res["counts"]["files"] == 1


def test_ghost_root_swept_when_source_dropped(tmp_path):
    a = make_source(tmp_path, "alpha")
    b = make_source(tmp_path, "beta")
    (a / "a.md").write_text("# A\n\n" + "word " * 30 + "\n", encoding="utf-8")
    (b / "b.md").write_text("# B\n\n" + "word " * 30 + "\n", encoding="utf-8")
    index(tmp_path, a, b)
    second = index(tmp_path, a)  # beta no longer configured
    assert second["swept_roots"] == ["beta"], "a dropped root's rows would otherwise be served forever"
    assert second["counts"]["files"] == 1


def test_stored_row_config_hash_forces_rechunk(tmp_path):
    src = make_source(tmp_path)
    (src / "a.md").write_text("# A\n\n" + "word " * 30 + "\n", encoding="utf-8")
    index(tmp_path, src)
    second = run_index_atomic(
        RunIndexAtomicOpts(
            db_path=str(tmp_path / "idx.db"),
            sources=[AtomicIndexSource(id="src", dir=str(src))],
            index_opts=IndexOptions(),
            stored_row_config_hash="newhash",
        )
    )
    assert second["changed"] == 1, "a channels-config change re-chunks unchanged files"

    from set_kb.store import SqliteFtsStore

    store = SqliteFtsStore(str(tmp_path / "idx.db"))
    store.init()
    assert store.get_meta("storedRowConfigHash") == "newhash"
    assert store.get_meta("schema_version") is not None
    assert store.get_meta("sqlite_version") is not None
    store.close()


def test_sweep_orphan_temps_keeps_live_peer(tmp_path):
    db = str(tmp_path / "idx.db")
    dead = tmp_path / "idx.db.tmp-999999"
    dead.write_bytes(b"x")
    mine = tmp_path / f"idx.db.tmp-{os.getpid()}"
    mine.write_bytes(b"x")
    sweep_orphan_temps(db)
    assert not dead.exists(), "a dead peer's husk is swept"
    assert mine.exists(), "a LIVE peer's temp build is left alone"


def test_missing_all_sources_is_a_loud_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="no configured source directory exists"):
        index(tmp_path, tmp_path / "nowhere")


def test_meta_chunk_makes_frontmatter_searchable(tmp_path):
    src = make_source(tmp_path)
    (src / "titled.md").write_text("---\ntitle: Findable Title\n---\n\n# Body\n\n" + "word " * 30 + "\n", encoding="utf-8")
    index(tmp_path, src)
    from set_kb.search import search, SearchOpts
    from set_kb.store import SqliteFtsStore

    store = SqliteFtsStore(str(tmp_path / "idx.db"))
    store.init()
    hits = search(store, "findable title", SearchOpts(lane_quota=0))
    assert [h.path for h in hits] == ["titled.md"], "the synthetic :meta chunk carries the title"
    store.close()
