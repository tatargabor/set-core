# Ported from an MIT-licensed upstream retrieval engine — see LICENSE-UPSTREAM in this package for the notice, the upstream commit and the port lineage.
"""Default storage backend: SQLite FTS5 over the stdlib ``sqlite3`` module.

Zero runtime deps beyond the standard library. FTS5 availability is probed by
`set_kb.runtime` BEFORE any store is opened — there is no unranked fallback.

⚠⚠ THE COLUMN ORDER IS THE bm25() WEIGHT ORDER. `bm25(chunks, w1, …, wN)`
binds weights to columns BY POSITION, and measured with SQLite it does NOT
throw on a wrong arity: one weight short returns the same numbers, one weight
long returns DIFFERENT ones — silently. So the column list and the weight list
are generated from the SAME arrays here, and `bm25_weights` asserts the arity
rather than trusting a hand-counted run of zeros. Adding a column means adding
it to one of these arrays; nothing else has to be counted by hand.
"""

from __future__ import annotations

import logging
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

from set_kb.types import Chunk, FileState, Filter, GraphEdge, GraphNode, PropertyRow

logger = logging.getLogger(__name__)

# Bump when the chunks schema/behavior changes so an existing DB reindexes
# once on open. ⚠ FTS5 has no `ALTER TABLE ADD COLUMN`, so a version bump that
# changes the COLUMN SET cannot be satisfied by re-chunking into the old table
# — `indexer.run_index_atomic` rebuilds the table from scratch for exactly
# this reason.
# 4 = files gained `size` — the incremental cheap-check compares mtime AND
# size now; a preserved-mtime content swap used to be skipped forever with the
# stale body served.
# 5 = chunks gained `scope` (design D9: the value captured from the path by a
# scope pattern, stored per chunk and filtered with `--scope`).
SCHEMA_VERSION = 5

FTS_UNINDEXED_COLUMNS = [
    "root",
    "path",
    "chunk_id",
    "doc_type",
    "parent_chunk_id",
    "level",
    "body_hash",
    "channel",
    "scope",
]
FTS_RANKED_COLUMNS = ["heading_path", "heading", "body"]
FTS_COLUMNS = FTS_UNINDEXED_COLUMNS + FTS_RANKED_COLUMNS


def bm25_weights(heading_path: float, heading: float, body: float) -> str:
    """The `bm25()` weight list for the ranked field weights — one weight per
    FTS5 column, unindexed columns pinned to 0. Raises on an arity mismatch,
    which is the only way this class of bug can ever be loud."""
    weights = [0] * len(FTS_UNINDEXED_COLUMNS) + [heading_path, heading, body]
    if len(weights) != len(FTS_COLUMNS):
        raise ValueError(f"kb: bm25 weight arity {len(weights)} != FTS5 column count {len(FTS_COLUMNS)}")
    return ",".join(str(w) for w in weights)


# 0-based FTS5 column index of `body`, the `snippet()` argument. Derived, not
# hand-written: a stale literal here is exactly as silent as a stale bm25
# arity — it would snippet the WRONG column and nothing would error.
BODY_COLUMN_INDEX = FTS_COLUMNS.index("body")

DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
  {unindexed},
  {ranked},
  tokenize='porter unicode61'
);
CREATE TABLE IF NOT EXISTS files (
  root TEXT, path TEXT, mtime_ms REAL, size INTEGER, sha256 TEXT,
  PRIMARY KEY (root, path)
);
CREATE TABLE IF NOT EXISTS nodes (
  id INTEGER PRIMARY KEY, type TEXT, name TEXT, path TEXT,
  UNIQUE(type, name)
);
CREATE TABLE IF NOT EXISTS edges (
  src INTEGER, dst INTEGER, rel TEXT, weight REAL DEFAULT 1,
  PRIMARY KEY (src, dst, rel)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE TABLE IF NOT EXISTS properties (
  root TEXT, path TEXT, key TEXT,
  value TEXT, value_num REAL, value_date TEXT, value_raw TEXT
);
-- The unique index doubles as the (root,path) lookup for delete-by-path (its
-- leading columns), so no separate idx_props_path is needed — one fewer index
-- to maintain on the hot per-file insert path.
CREATE UNIQUE INDEX IF NOT EXISTS idx_props_uniq ON properties(root, path, key, value);
CREATE INDEX IF NOT EXISTS idx_props_kv ON properties(key, value);
CREATE TABLE IF NOT EXISTS kb_meta (k TEXT PRIMARY KEY, v TEXT);
""".format(unindexed=", ".join(f"{c} UNINDEXED" for c in FTS_UNINDEXED_COLUMNS), ranked=", ".join(FTS_RANKED_COLUMNS))


def build_filter_clauses(filters, outer: str):
    """Correlated EXISTS predicates for facet filters. All values are bound as
    parameters (never interpolated) — SQL-injection guard."""
    clauses: list[str] = []
    args: list = []

    def norm(v):
        return str(v).lower().strip()

    def eq_col(t):
        return "value_num" if t == "number" else "value_date" if t == "date" else "value"

    def eq_val(t, v):
        if t == "number":
            return float(v)
        if t == "date":
            return str(v)
        return norm(v)

    for f in filters or []:
        if f.op == "eq" and f.value is not None:
            col = eq_col(f.type)
            clauses.append(f"EXISTS (SELECT 1 FROM properties p WHERE p.root={outer}.root AND p.path={outer}.path AND p.key=? AND p.{col}=?)")
            args.extend([f.key, eq_val(f.type, f.value)])
        elif f.op == "in" and f.values:
            col = eq_col(f.type)
            ph = ",".join("?" for _ in f.values)
            clauses.append(f"EXISTS (SELECT 1 FROM properties p WHERE p.root={outer}.root AND p.path={outer}.path AND p.key=? AND p.{col} IN ({ph}))")
            args.append(f.key)
            args.extend(eq_val(f.type, v) for v in f.values)
        elif f.op in ("gte", "lte") and f.value is not None:
            col = "value_num" if f.type == "number" else "value_date" if f.type == "date" else "value"
            cmp = ">=" if f.op == "gte" else "<="
            clauses.append(f"EXISTS (SELECT 1 FROM properties p WHERE p.root={outer}.root AND p.path={outer}.path AND p.key=? AND p.{col} IS NOT NULL AND p.{col} {cmp} ?)")
            args.append(f.key)
            args.append(float(f.value) if f.type == "number" else str(f.value) if f.type == "date" else norm(f.value))
    return clauses, args


class SqliteFtsStore:
    """The storage seam over sqlite3. Schema + change detection + CRUD + the
    IDF machinery the coverage rerank needs. Ranking lives in `set_kb.search`."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path, isolation_level=None)  # explicit BEGIN/COMMIT below
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        # Let a concurrent reader (e.g. a stats poll during a reindex) wait
        # briefly for a batch's write lock instead of failing with SQLITE_BUSY.
        self.db.execute("PRAGMA busy_timeout=5000")
        self._stem_ready: Optional[bool] = None
        self._stem_cache: dict = {}
        self._df_cache: dict = {}
        self._vocab_ready: Optional[bool] = None

    def init(self) -> None:
        self.db.executescript(DDL)

    def begin(self) -> None:
        self.db.execute("BEGIN")

    def commit(self) -> None:
        self.db.execute("COMMIT")
        # An index batch just changed the corpus; cached document frequencies
        # (and therefore IDF) are stale. The fts5vocab view itself is live.
        self._df_cache.clear()

    def rollback(self) -> None:
        try:
            self.db.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass

    def close(self) -> None:
        self.db.close()

    def finalize_rename(self, dest: str) -> None:
        """Finalize a temp-path build onto `dest`. WAL ordering is load-bearing:
        TRUNCATE-checkpoint + close BEFORE the rename so the single main file
        holds every committed page; then rename atomically and drop stale
        sidecars — the DESTINATION's sidecars too: on a schema REBUILD the file
        we just replaced had its own, and a WAL left beside a different main
        file is not stale data — SQLite would try to recover from it on the
        next open."""
        try:
            self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        self.db.close()
        os.replace(self.db_path, dest)
        for ext in ("-wal", "-shm"):
            for p in (self.db_path + ext, dest + ext):
                try:
                    os.unlink(p)
                except FileNotFoundError:
                    pass

    def close_and_unlink(self) -> None:
        """Close and remove this DB file + WAL sidecars — cleanup for a failed
        run that itself created the file (never touches a pre-existing valid DB)."""
        try:
            self.db.close()
        except sqlite3.Error:
            pass
        for ext in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db_path + ext)
            except FileNotFoundError:
                pass

    # ── change detection ──

    def get_file_state(self, root: str, path: str) -> Optional[FileState]:
        r = self.db.execute("SELECT mtime_ms, size, sha256 FROM files WHERE root=? AND path=?", (root, path)).fetchone()
        return FileState(mtime_ms=r["mtime_ms"], size=r["size"], sha256=r["sha256"]) if r else None

    def set_file_state(self, root: str, path: str, s: FileState) -> None:
        self.db.execute(
            "INSERT INTO files(root,path,mtime_ms,size,sha256) VALUES(?,?,?,?,?) "
            "ON CONFLICT(root,path) DO UPDATE SET mtime_ms=excluded.mtime_ms, size=excluded.size, sha256=excluded.sha256",
            (root, path, s.mtime_ms, s.size, s.sha256),
        )

    def list_paths(self, root: str) -> list:
        return [r["path"] for r in self.db.execute("SELECT path FROM files WHERE root=?", (root,))]

    def roots(self) -> list:
        """Distinct roots that have files in the store — the ghost-root sweep
        compares this against the roots of the CURRENT run."""
        return [r["root"] for r in self.db.execute("SELECT DISTINCT root FROM files ORDER BY root")]

    def delete_by_root(self, root: str) -> None:
        """Remove every trace of a ROOT (chunks, properties, file states) — for
        a root that no longer takes part in indexing. Without this the root's
        rows are indexed FOREVER: every search keeps serving them, with no
        signal that the source is gone. Graph nodes/edges are shared across
        roots by path and deliberately left."""
        self._df_cache.clear()
        self.db.execute("DELETE FROM chunks WHERE root=?", (root,))
        self.db.execute("DELETE FROM properties WHERE root=?", (root,))
        self.db.execute("DELETE FROM files WHERE root=?", (root,))

    def delete_by_path(self, root: str, path: str) -> None:
        self._df_cache.clear()
        # chunks includes the file's synthetic `:meta` chunk (same path) — removed here.
        self.db.execute("DELETE FROM chunks WHERE root=? AND path=?", (root, path))
        # outbound edges originate from this file's nodes; prune nodes owned by path then dangling edges
        for n in self.db.execute("SELECT id FROM nodes WHERE path=?", (path,)).fetchall():
            self.db.execute("DELETE FROM edges WHERE src=? OR dst=?", (n["id"], n["id"]))
        self.db.execute("DELETE FROM nodes WHERE path=?", (path,))
        self.db.execute("DELETE FROM properties WHERE root=? AND path=?", (root, path))
        self.db.execute("DELETE FROM files WHERE root=? AND path=?", (root, path))

    # ── properties (facet frontmatter) ──

    def delete_properties_by_path(self, root: str, path: str) -> None:
        self.db.execute("DELETE FROM properties WHERE root=? AND path=?", (root, path))

    def insert_property(self, r: PropertyRow) -> None:
        # INSERT OR IGNORE + UNIQUE(root,path,key,value) de-dups within-file duplicates.
        self.db.execute(
            "INSERT OR IGNORE INTO properties(root,path,key,value,value_num,value_date,value_raw) VALUES(?,?,?,?,?,?,?)",
            (r.root, r.path, r.key, r.value, r.value_num, r.value_date, r.value_raw),
        )

    def facets(self, keys, opts: Optional[dict] = None) -> dict:
        out: dict = {}
        if not keys:
            return out
        opts = opts or {}
        where = [f"key IN ({','.join('?' for _ in keys)})"]
        args: list = list(keys)
        if opts.get("root"):
            where.append("o.root = ?")
            args.append(opts["root"])
        clauses, fargs = build_filter_clauses(opts.get("filters"), "o")
        where.extend(clauses)
        args.extend(fargs)
        # Distinct FILES, not rows: two sources with the same relative path are
        # two files, so count distinct (root,path).
        sql = f"SELECT key, value, COUNT(DISTINCT root || char(31) || path) n FROM properties o WHERE {' AND '.join(where)} GROUP BY key, value"
        for r in self.db.execute(sql, args):
            out.setdefault(r["key"], {})[r["value"]] = r["n"]
        return out

    # ── schema lifecycle meta ──

    def get_user_version(self) -> int:
        return int(self.db.execute("PRAGMA user_version").fetchone()["user_version"])

    def set_user_version(self, v: int) -> None:
        # PRAGMA does not accept a bound parameter; v is an internal integer constant.
        self.db.execute(f"PRAGMA user_version = {int(v)}")

    def get_meta(self, k: str) -> Optional[str]:
        r = self.db.execute("SELECT v FROM kb_meta WHERE k=?", (k,)).fetchone()
        return r["v"] if r else None

    def set_meta(self, k: str, v: str) -> None:
        self.db.execute("INSERT INTO kb_meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    # ── indexing ──

    def insert_chunk(self, c: Chunk) -> None:
        self.db.execute(
            "INSERT INTO chunks(root,path,chunk_id,doc_type,parent_chunk_id,level,body_hash,channel,scope,heading_path,heading,body) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                c.root,
                c.path,
                c.chunk_id,
                c.doc_type,
                c.parent_chunk_id,
                c.level,
                c.body_hash,
                c.channel,
                c.scope,
                c.heading_path,
                c.heading,
                c.body,
            ),
        )

    def add_node(self, n: GraphNode) -> None:
        self.db.execute(
            "INSERT INTO nodes(type,name,path) VALUES(?,?,?) ON CONFLICT(type,name) DO UPDATE SET path=COALESCE(excluded.path, nodes.path)",
            (n.type, n.name, n.path),
        )

    def add_edge(self, e: GraphEdge) -> None:
        src = self.db.execute("SELECT id FROM nodes WHERE name=? LIMIT 1", (e.src,)).fetchone()
        dst = self.db.execute("SELECT id FROM nodes WHERE name=? LIMIT 1", (e.dst,)).fetchone()
        if not src or not dst:
            return
        self.db.execute(
            "INSERT OR IGNORE INTO edges(src,dst,rel,weight) VALUES(?,?,?,?)", (src["id"], dst["id"], e.rel, e.weight)
        )

    # ── IDF machinery (coverage rerank / PRF) ──

    def _stems(self, tokens: list) -> dict:
        """Porter stems for raw tokens, computed by SQLite's OWN tokenizer so
        they match what FTS5 actually indexed. A raw token is NOT a usable key
        into the vocab table: FTS5 stores the stem, and no prefix range anchored
        at the raw token can reach a key that sorts before it. The helper
        tables live in `temp.`, so this works against a read-only main DB."""
        out: dict = {}
        missing = [t for t in dict.fromkeys(tokens) if t not in self._stem_cache]
        if self._stem_ready is None:
            try:
                self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.kb_stem USING fts5(t, tokenize='porter unicode61')")
                self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.kb_stem_vocab USING fts5vocab(kb_stem, 'instance')")
                self._stem_ready = True
            except sqlite3.Error:
                self._stem_ready = False
        if self._stem_ready and missing:
            try:
                self.db.execute("DELETE FROM temp.kb_stem")
                for i, t in enumerate(missing):
                    self.db.execute("INSERT INTO temp.kb_stem(rowid, t) VALUES(?,?)", (i + 1, t))
                # 'instance' carries the source rowid, so each stem maps back to its token.
                for r in self.db.execute("SELECT term, doc FROM temp.kb_stem_vocab"):
                    tok = missing[(int(r["doc"]) or 0) - 1] if r["doc"] else None
                    if tok is not None:
                        self._stem_cache[tok] = str(r["term"])
            except sqlite3.Error:
                logger.debug("kb: stemming unavailable, falling back to raw tokens")
        for t in tokens:
            out[t] = self._stem_cache.get(t, t)
        return out

    def document_frequencies(self, tokens: list) -> dict:
        """Corpus document frequency for raw tokens, via the fts5vocab shadow
        table. Keys are exact porter stems (see `_stems`), so df is exact rather
        than a prefix over-estimate. `fts5vocab` is a live view over the FTS
        index, but `_df_cache` is not — it is dropped on commit/delete_by_path,
        the points at which an index batch can have moved the counts. Falls
        back to df=0 when the vocab table cannot be created."""
        out: dict = {}
        stem = self._stems(tokens)
        keys = [stem[t] for t in tokens]
        missing = [k for k in dict.fromkeys(keys) if k not in self._df_cache]
        if self._vocab_ready is None:
            try:
                self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vocab USING fts5vocab(chunks, 'row')")
                self._vocab_ready = True
            except sqlite3.Error:
                self._vocab_ready = False
        if self._vocab_ready and missing:
            ph = ",".join("?" for _ in missing)
            try:
                for k in missing:
                    self._df_cache[k] = 0  # absent term = df 0
                for r in self.db.execute(f"SELECT term, doc FROM chunks_vocab WHERE term IN ({ph})", missing):
                    self._df_cache[str(r["term"])] = int(r["doc"]) or 0
            except sqlite3.Error:
                logger.debug("kb: vocab unusable, df treated as 0")
        for t in tokens:
            out[t] = self._df_cache.get(stem[t], 0)
        return out

    def idf(self, tokens: list) -> dict:
        """IDF weights for the given tokens over the current corpus."""
        n = max(1, self.counts()["chunks"])
        df = self.document_frequencies(tokens)
        return {t: math.log(1 + n / (1 + df.get(t, 0))) for t in tokens}

    # ── query-side fetches ──

    def get_chunk(self, root: str, path: str, heading_path: Optional[str] = None) -> Optional[Chunk]:
        """Fetch a chunk by path (+ optional section). A path-only fetch of a
        multi-chunk file returns the FIRST chunk plus a `suppressed_sections`
        count — it must never silently hand back one arbitrary slice of N."""
        if heading_path:
            r = self.db.execute(
                "SELECT * FROM chunks WHERE root=? AND path=? AND heading_path=? LIMIT 1", (root, path, heading_path)
            ).fetchone()
            return _row_to_chunk(r) if r else None
        r = self.db.execute("SELECT * FROM chunks WHERE root=? AND path=? ORDER BY rowid LIMIT 1", (root, path)).fetchone()
        if not r:
            return None
        n = self.db.execute("SELECT COUNT(*) n FROM chunks WHERE root=? AND path=?", (root, path)).fetchone()["n"]
        c = _row_to_chunk(r)
        c.suppressed_sections = max(0, n - 1)
        return c

    def get_chunks(self, root: str, path: str) -> list:
        """All chunks of a file in document order — the non-truncating
        companion to a path-only `get_chunk`."""
        return [
            _row_to_chunk(r)
            for r in self.db.execute("SELECT * FROM chunks WHERE root=? AND path=? ORDER BY rowid", (root, path))
        ]

    def get_chunk_by_id(self, root: str, chunk_id: str) -> Optional[Chunk]:
        r = self.db.execute("SELECT * FROM chunks WHERE root=? AND chunk_id=? LIMIT 1", (root, chunk_id)).fetchone()
        return _row_to_chunk(r) if r else None

    def snippet_fallback(self, root: str, path: str, body: str) -> str:
        """Fill-in for a BLANK snippet: the body head, or — for a bodyless
        `:meta` record — the head of the file's first non-empty chunk (a
        document preview at file granularity). One indexed query, and only on
        this degraded path."""
        b = body or ""
        if b.strip():
            return re.sub(r"\s+", " ", b).strip()[:200]
        r = self.db.execute(
            "SELECT body FROM chunks WHERE root=? AND path=? AND TRIM(body)<>'' ORDER BY rowid LIMIT 1", (root, path)
        ).fetchone()
        return re.sub(r"\s+", " ", r["body"]).strip()[:200] if r else ""

    def counts(self) -> dict:
        def c(q):
            return self.db.execute(q).fetchone()["n"]

        return {
            "files": c("SELECT COUNT(*) n FROM files"),
            "chunks": c("SELECT COUNT(*) n FROM chunks"),
            "nodes": c("SELECT COUNT(*) n FROM nodes"),
            "edges": c("SELECT COUNT(*) n FROM edges"),
        }


def _row_to_chunk(r) -> Chunk:
    return Chunk(
        root=r["root"],
        path=r["path"],
        chunk_id=r["chunk_id"],
        heading_path=r["heading_path"],
        heading=r["heading"],
        level=r["level"],
        parent_chunk_id=r["parent_chunk_id"],
        doc_type=r["doc_type"],
        channel=r["channel"],
        scope=r["scope"],
        body=r["body"],
        body_hash=r["body_hash"],
    )
