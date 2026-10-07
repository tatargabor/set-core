"""Store: schema, the bm25 weight/column binding, meta, and chunk fetches."""

from __future__ import annotations

import sqlite3

import pytest

from set_kb import store as store_mod
from set_kb.store import BODY_COLUMN_INDEX, FTS_COLUMNS, SCHEMA_VERSION, SqliteFtsStore, bm25_weights
from set_kb.types import Chunk


@pytest.fixture()
def store(tmp_path):
    s = SqliteFtsStore(str(tmp_path / "idx.db"))
    s.init()
    yield s
    s.close()


def _chunk(**over):
    base = dict(
        root="r",
        path="a.md",
        chunk_id="deadbeef:0",
        heading_path="A",
        heading="A",
        level=1,
        parent_chunk_id=None,
        doc_type="doc",
        body="alpha beta",
        body_hash="h0",
        channel=None,
    )
    base.update(over)
    return Chunk(**base)


def test_bm25_weights_bind_to_column_order():
    # 9 unindexed columns pinned to 0, then headingPath/heading/body.
    assert len(FTS_COLUMNS) == 12
    assert bm25_weights(10, 3, 1) == "0,0,0,0,0,0,0,0,0,10,3,1"


def test_bm25_weight_arity_is_loud(monkeypatch):
    """A weight list that disagrees with the column count RAISES — the silent
    arity mismatch is exactly the bug class the derived list exists to close."""
    monkeypatch.setattr(store_mod, "FTS_COLUMNS", store_mod.FTS_COLUMNS[:-1])
    with pytest.raises(ValueError, match="arity"):
        bm25_weights(10, 3, 1)


def test_body_column_index_is_derived():
    assert FTS_COLUMNS[BODY_COLUMN_INDEX] == "body"


def test_fts5_tokenizer_is_porter_unicode61(store):
    row = store.db.execute("SELECT sql FROM sqlite_master WHERE name='chunks'").fetchone()
    assert "porter unicode61" in row["sql"]


def test_store_records_schema_and_sqlite_version(tmp_path):
    s = SqliteFtsStore(str(tmp_path / "idx.db"))
    s.init()
    s.set_user_version(SCHEMA_VERSION)
    s.set_meta("schema_version", str(SCHEMA_VERSION))
    s.set_meta("sqlite_version", sqlite3.sqlite_version)
    assert s.get_user_version() == SCHEMA_VERSION
    assert s.get_meta("schema_version") == str(SCHEMA_VERSION)
    assert s.get_meta("sqlite_version") == sqlite3.sqlite_version
    assert s.get_meta("absent") is None
    s.close()


def test_file_state_roundtrip_and_counts(store):
    store.begin()
    store.insert_chunk(_chunk())
    from set_kb.types import FileState

    store.set_file_state("r", "a.md", FileState(mtime_ms=1.0, size=10, sha256="x"))
    store.commit()
    st = store.get_file_state("r", "a.md")
    assert st is not None and st.sha256 == "x" and st.size == 10
    assert store.list_paths("r") == ["a.md"]
    counts = store.counts()
    assert counts["files"] == 1 and counts["chunks"] == 1


def test_get_chunk_path_only_reports_suppressed_sections(store):
    store.begin()
    store.insert_chunk(_chunk(chunk_id="deadbeef:0", heading_path="A"))
    store.insert_chunk(_chunk(chunk_id="deadbeef:1", heading_path="A > B", heading="B"))
    store.commit()
    c = store.get_chunk("r", "a.md")
    assert c is not None and c.heading_path == "A"
    assert c.suppressed_sections == 1  # one more chunk exists, not returned
    exact = store.get_chunk("r", "a.md", heading_path="A > B")
    assert exact is not None and exact.chunk_id == "deadbeef:1"
    assert store.get_chunk("r", "missing.md") is None


def test_delete_by_path_removes_all_traces(store):
    from set_kb.types import FileState, GraphEdge, GraphNode, PropertyRow

    store.begin()
    store.insert_chunk(_chunk())
    store.add_node(GraphNode(type="file", name="a.md", path="a.md"))
    store.add_edge(GraphEdge(src="a.md", dst="b.md", rel="links_to"))
    store.insert_property(PropertyRow(root="r", path="a.md", key="k", value="v", value_raw="v"))
    store.set_file_state("r", "a.md", FileState(mtime_ms=1.0, size=1, sha256="x"))
    store.commit()
    store.delete_by_path("r", "a.md")
    assert store.get_file_state("r", "a.md") is None
    assert store.counts()["chunks"] == 0
    remaining = store.db.execute("SELECT COUNT(*) n FROM nodes WHERE path='a.md'").fetchone()["n"]
    assert remaining == 0


def test_wal_and_busy_timeout_are_set(tmp_path):
    s = SqliteFtsStore(str(tmp_path / "idx.db"))
    mode = s.db.execute("PRAGMA journal_mode").fetchone()[0]
    timeout = s.db.execute("PRAGMA busy_timeout").fetchone()[0]
    assert mode == "wal"
    assert timeout == 5000
    s.close()
