# Ported from an MIT-licensed upstream retrieval engine — see LICENSE-UPSTREAM in this package for the notice, the upstream commit and the port lineage.
"""Indexer: walk a filesystem source, layered mtime→sha256 change detection,
structural chunking, tier-1 graph extraction, transactional upsert; plus the
atomic index-run orchestration (`run_index_atomic`).

Divergences carried by this port, both deliberate:
- the walk sorts directory entries (the reference reads them in OS order) so
  insertion order — and therefore rowid order — is reproducible;
- paths are NFC-normalised before indexing, so an accented file name walked on
  different machines yields the same key (design D2 of the change).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Optional

from set_kb.channels import ChannelRule, classify_channel, compile_channel_rules
from set_kb.chunker import chunk_markdown
from set_kb.frontmatter import DEFAULT_FACET_KEYS, DEFAULT_SEARCHABLE_KEYS, build_meta, build_properties
from set_kb.glob import glob_to_re, match_any
from set_kb.store import SCHEMA_VERSION, SqliteFtsStore
from set_kb.types import Chunk, DocType, FileState, GraphEdge, GraphNode, PropertyRow

logger = logging.getLogger(__name__)


@dataclass
class IndexSource:
    root: str  # label/id stored on chunks
    dir: str  # absolute directory to walk
    include: Optional[Callable[[str], bool]] = None


@dataclass
class IndexOptions:
    force: bool = False
    index_agents_files: bool = True  # AGENTS.md / CLAUDE.md
    include_source_markdown: bool = True  # *.md in source dirs → doc_type 'source-md'
    include: Optional[list] = None  # glob patterns to include
    exclude: Optional[list] = None  # glob patterns to exclude
    extensions: Optional[list] = None  # e.g. [".md"]
    # frontmatter structural indexing routing
    frontmatter: Optional[dict] = None  # {searchableKeys, facetKeys}
    # Channel classification rules. Absent = every chunk gets channel None,
    # and the reserved lane simply finds nothing — the engine degrades to no
    # lane rather than misclassifying.
    channels: Optional[list] = None


@dataclass
class IndexStats:
    scanned: int = 0
    changed: int = 0
    deleted: int = 0
    chunks: int = 0
    parse_failures: int = 0  # files whose frontmatter block was present but did not parse
    # Files whose stat/read threw (broken symlink, permission) — counted and
    # skipped INSTEAD of aborting the whole source. Only the stat/read phase is
    # isolated; a failure AFTER the first store mutation still rolls the
    # source back (whole-run semantics kept).
    read_failures: int = 0
    missing: bool = False  # source dir did not exist → skipped (degrade, not abort)


DEFAULT_EXCLUDE = re.compile(r"(^|/)(node_modules|\.git|dist|build|\.next|coverage|\.kb)(/|$)")

# Files processed between batch commits. Committing per batch also releases
# the WAL write lock so a concurrent reader is served.
YIELD_EVERY = 100


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _walk(dir: str, base: str, out: list) -> list:
    try:
        entries = sorted(os.scandir(dir), key=lambda e: e.name)
    except FileNotFoundError:
        return out
    for e in entries:
        abs = os.path.join(dir, e.name)
        rel = os.path.relpath(abs, base).replace(os.sep, "/")
        if DEFAULT_EXCLUDE.search(rel):
            continue
        if e.is_dir(follow_symlinks=False):
            _walk(abs, base, out)
        elif re.search(r"\.(md|mdx|markdown)$", e.name, re.IGNORECASE):
            out.append(abs)
    return out


def doc_type_of(rel: str, include_source_markdown: bool) -> DocType:
    base = rel.rsplit("/", 1)[-1]
    # `<File>.AGENTS.md` = per-file index sidecar. Classified `agents` so it is
    # searchable, but its name != "AGENTS.md" so a native up-walk never
    # auto-injects it (pull-only via kb search).
    if base in ("AGENTS.override.md", "AGENTS.md", "CLAUDE.md") or base.endswith(".AGENTS.md"):
        return "agents"
    if include_source_markdown and re.search(r"(^|/)(src|lib|app|packages)/", rel):
        return "source-md"
    return "doc"


def index_source(store: SqliteFtsStore, src: IndexSource, opts: Optional[IndexOptions] = None) -> IndexStats:
    """Index one source directory into the store. Layered change detection:
    a cheap mtime+size check, then sha256; changed files are re-chunked,
    deleted files removed."""
    opts = opts or IndexOptions()
    # A configured source whose dir is absent degrades to skip-with-warning
    # rather than throwing mid-walk. A partial source set still indexes what
    # exists.
    if not os.path.isdir(src.dir):
        logger.warning("kb index: source directory does not exist, skipping: %s", src.dir)
        return IndexStats(missing=True)

    exts = opts.extensions or []
    if exts:
        ext_re = re.compile("(" + "|".join(e.replace(".", "\\.") for e in exts) + ")$", re.IGNORECASE)
    else:
        ext_re = re.compile(r"\.(md|mdx|markdown)$", re.IGNORECASE)
    inc = [glob_to_re(p) for p in opts.include] if opts.include else None
    exc = [glob_to_re(p) for p in opts.exclude] if opts.exclude else None
    include_source_md = opts.include_source_markdown
    # Compiled once per source: glob compilation per file would be a measurable
    # walk cost.
    channel_rules = compile_channel_rules(opts.channels)
    files = []
    for abs in _walk(src.dir, src.dir, []):
        rel = os.path.relpath(abs, src.dir).replace(os.sep, "/")
        if src.include and not src.include(rel):
            continue
        if inc and not match_any(inc, rel):
            continue
        if exc and match_any(exc, rel):
            continue
        if doc_type_of(rel, include_source_md) == "agents" and opts.index_agents_files is False:
            continue
        files.append(abs)

    stats = IndexStats(scanned=len(files))
    live: set = set()
    fm_cfg = opts.frontmatter or {"searchableKeys": DEFAULT_SEARCHABLE_KEYS, "facetKeys": DEFAULT_FACET_KEYS}

    store.begin()
    try:
        since_batch = 0
        for abs in files:
            if since_batch >= YIELD_EVERY:
                store.commit()
                store.begin()
                since_batch = 0
            since_batch += 1
            rel = os.path.relpath(abs, src.dir).replace(os.sep, "/")
            rel = unicodedata.normalize("NFC", rel)
            live.add(rel)
            # stat/read/sha run BEFORE any store mutation, so a per-file
            # failure here can just skip the file.
            try:
                st = os.stat(abs)
                with open(abs, "rb") as f:
                    buf = f.read()
                digest = _sha_bytes(buf)
            except OSError as err:
                stats.read_failures += 1
                logger.warning("kb index: file unreadable, skipped: %s (%s)", rel, err)
                continue
            mtime_ms = st.st_mtime_ns / 1_000_000
            prev = store.get_file_state(src.root, rel)
            # Cheap-check on mtime AND size: mtime alone skipped a
            # mtime-preserving content swap (cp -p / rsync -a / restore) forever.
            if not opts.force and prev and prev.mtime_ms == mtime_ms and prev.size == st.st_size:
                continue
            if not opts.force and prev and prev.sha256 == digest:
                store.set_file_state(src.root, rel, FileState(mtime_ms=mtime_ms, size=st.st_size, sha256=digest))
                continue  # content unchanged
            # changed → replace
            store.delete_by_path(src.root, rel)
            dt = doc_type_of(rel, include_source_md)
            # Classified from the root AND the root-relative path. Computed per
            # FILE, not per chunk: every section of a file shares its origin.
            channel = classify_channel(channel_rules, src.root, rel)
            parsed = chunk_markdown(root=src.root, path=rel, text=buf.decode("utf-8"), doc_type=dt)
            chunks = parsed.chunks
            # file node
            store.add_node(GraphNode(type="file", name=rel, path=rel))
            for c in chunks:
                c.channel = channel
                store.insert_chunk(c)
                if c.level > 0:
                    store.add_node(GraphNode(type="heading", name=c.heading_path, path=rel))
                    parent_chunk = next((x for x in chunks if x.chunk_id == c.parent_chunk_id), None)
                    parent_name = parent_chunk.heading_path if parent_chunk else rel
                    store.add_edge(GraphEdge(src=c.heading_path, dst=parent_name, rel="child_of"))
            # tier-1 graph: wikilinks + md links + frontmatter tags
            for w in parsed.wikilinks:
                target = _normalize_link(w)
                store.add_node(GraphNode(type="file", name=target, path=None))
                store.add_edge(GraphEdge(src=rel, dst=target, rel="links_to"))
            for l in parsed.md_links:
                target = _normalize_rel(rel, l)
                store.add_node(GraphNode(type="file", name=target, path=None))
                store.add_edge(GraphEdge(src=rel, dst=target, rel="references"))
            frontmatter = parsed.frontmatter
            if frontmatter is not None:
                tags = frontmatter.get("tags")
                if isinstance(tags, list):
                    for tag in tags:
                        store.add_node(GraphNode(type="tag", name=f"tag:{tag}", path=None))
                        store.add_edge(GraphEdge(src=rel, dst=f"tag:{tag}", rel="has_tag"))
                # Searchable meta needs only insertChunk (required); it must
                # NOT be gated on the optional property insert, or a
                # chunk-capable store would silently lose title/description search.
                meta = build_meta(frontmatter, fm_cfg.get("searchableKeys", DEFAULT_SEARCHABLE_KEYS))
                title, meta_body = meta["title"], meta["body"]
                meta_text = "\n".join([title or "", meta_body]).strip()
                if meta_text:
                    heading = title if title is not None else re.sub(r"\.(md|mdx|markdown)$", "", rel.rsplit("/", 1)[-1], flags=re.IGNORECASE)
                    store.insert_chunk(
                        Chunk(
                            root=src.root,
                            path=rel,
                            chunk_id=f"{_sha_bytes(rel.encode('utf-8'))[:8]}:meta",
                            heading_path=heading,
                            heading=heading,
                            level=0,
                            parent_chunk_id=None,
                            doc_type=dt,
                            channel=channel,
                            body=meta_body,
                            body_hash=_sha_bytes(meta_text.encode("utf-8")),
                        )
                    )
                    stats.chunks += 1
                for row in build_properties(frontmatter, fm_cfg.get("facetKeys", DEFAULT_FACET_KEYS)):
                    store.insert_property(PropertyRow(root=src.root, path=rel, **row))
            # Mirror docType for EVERY file (facetable regardless of frontmatter presence).
            store.insert_property(PropertyRow(root=src.root, path=rel, key="docType", value=dt, value_num=None, value_date=None, value_raw=dt))
            if parsed.parse_failed:
                stats.parse_failures += 1
            store.set_file_state(src.root, rel, FileState(mtime_ms=mtime_ms, size=st.st_size, sha256=digest))
            stats.changed += 1
            stats.chunks += len(chunks)
        # deletions: paths in store but not on disk
        for p in store.list_paths(src.root):
            if p not in live:
                store.delete_by_path(src.root, p)
                stats.deleted += 1
        store.commit()
    except BaseException:
        store.rollback()
        raise
    return stats


# ── atomic index-run orchestration ──
#
# Failure-atomicity guarantee: a file at `db_path` means a successful index
# ran. Branch on whether `db_path` already exists:
#   - First index (no db_path): build into `<db_path>.tmp-<pid>` and rename()
#     onto db_path only on success. A crash/OOM/SIGKILL leaves only the temp
#     orphan — the real path never appears. A create-track → close+unlink-on-
#     failure variant is NOT used: that cleanup is dead code under uncatchable
#     termination and would leave the husk.
#   - Incremental (valid db_path exists): index in place, preserving the in-DB
#     file-state incremental skip needs. A mid-run failure leaves the prior DB
#     valid & queryable; a re-run completes it.


@dataclass
class AtomicIndexSource:
    id: str
    dir: str


@dataclass
class RunIndexAtomicOpts:
    db_path: str
    sources: list  # of AtomicIndexSource
    index_opts: Optional[IndexOptions] = None
    # Sources came from an explicit source arg; a missing one is a user typo.
    explicit: bool = False
    # Schema-version reindex gate: a changed facet-config hash forces a one-time
    # full reindex.
    facet_config_hash: Optional[str] = None
    # Second stale-row gate: channels and the docType switches are STORED ON
    # ROWS, but only changed FILES were re-chunked — a channels-config edit
    # left the old labels on every unchanged file, and the reserved lane kept
    # filling by the stale classification. A changed hash forces a re-chunk.
    stored_row_config_hash: Optional[str] = None


@dataclass
class AtomicIndexStats(IndexStats):
    missing_roots: list = field(default_factory=list)  # configured sources whose dir did not exist
    swept_roots: list = field(default_factory=list)  # roots deleted because they are no longer indexed


def _is_process_alive(pid: int) -> bool:
    """True if `pid` names a live process (existence probe via signal 0).
    EPERM = alive but not ours; ESRCH/ProcessLookupError = dead. Signal 0 is a
    read-only liveness check, never a termination."""
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, OSError):
        return False


def sweep_orphan_temps(db_path: str) -> None:
    """Remove stale `<db_path>.tmp-*` orphans (+ WAL sidecars) left by a prior
    SIGKILL'd first-index run, so temp husks do not accumulate. A temp file
    whose PID names a LIVE process belongs to a concurrent peer run and is left
    alone — unlinking it would break that peer's finalize rename."""
    dir = os.path.dirname(db_path)
    prefix = f"{os.path.basename(db_path)}.tmp-"
    try:
        entries = os.listdir(dir)
    except FileNotFoundError:
        return
    for e in entries:
        if not e.startswith(prefix):
            continue
        # filename is `<base>.tmp-<pid>` or a `-wal`/`-shm` sidecar of it.
        pid_part = re.split(r"[.-]", e[len(prefix) :])[0]
        try:
            pid = int(pid_part)
        except ValueError:
            pid = 0
        if pid > 0 and _is_process_alive(pid):
            continue  # live peer
        try:
            os.unlink(os.path.join(dir, e))
        except OSError:
            pass


def run_index_atomic(opts: RunIndexAtomicOpts) -> dict:
    """Run an atomic index over all sources. Returns the merged stats plus the
    store counts. See the module docstring for the atomicity guarantee."""
    db_path = opts.db_path

    # An explicit source dir that does not exist is a typo → hard error, before
    # any store is opened (no husk possible).
    if opts.explicit:
        for s in opts.sources:
            if not os.path.isdir(s.dir):
                raise FileNotFoundError(f"kb index: --source directory does not exist: {s.dir}")

    # Every configured source dir absent → nothing indexable. Checked BEFORE
    # any store is opened so a first index never creates a temp husk here.
    if not any(os.path.isdir(s.dir) for s in opts.sources):
        raise FileNotFoundError("kb index: no configured source directory exists")

    sweep_orphan_temps(db_path)
    preexisting = os.path.exists(db_path)
    eff_opts = opts.index_opts or IndexOptions()

    # Schema-version / facet-config gate. The two stale states need DIFFERENT
    # treatments:
    #   - stale FACET/ROW CONFIG → the columns are fine, the rows are not: a
    #     forced full RE-CHUNK into the existing table is enough;
    #   - stale SCHEMA VERSION → the COLUMN SET changed, and FTS5 has no
    #     `ALTER TABLE ADD COLUMN`. Nothing about re-chunking into the old
    #     table fails loudly, so the table is REBUILT: index into a fresh temp
    #     DB and rename it over the old one, exactly like a first index. That
    #     also keeps the failure-atomicity guarantee — a crash mid-rebuild
    #     leaves the OLD, valid DB in place.
    if preexisting:
        probe = SqliteFtsStore(db_path)
        probe.init()
        ver = probe.get_user_version()
        stored_hash = probe.get_meta("facetConfigHash")
        stored_row_hash = probe.get_meta("storedRowConfigHash")
        probe.close()
        if ver < SCHEMA_VERSION:
            preexisting = False  # → build into a temp path and rename over the old DB
        elif (opts.facet_config_hash is not None and stored_hash != opts.facet_config_hash) or (
            opts.stored_row_config_hash is not None and stored_row_hash != opts.stored_row_config_hash
        ):
            eff_opts = IndexOptions(**{**eff_opts.__dict__, "force": True})

    target = db_path if preexisting else f"{db_path}.tmp-{os.getpid()}"
    if not preexisting:
        # A recycled pid can name a temp husk left by a SIGKILL'd earlier run —
        # sweep_orphan_temps keeps it (OUR pid looks like a live peer), and
        # opening it as the build target would build into a foreign-schema
        # file. We are about to create this path fresh: remove any husk first.
        for suf in ("", "-wal", "-shm"):
            try:
                os.unlink(f"{target}{suf}")
            except FileNotFoundError:
                pass

    store = SqliteFtsStore(target)
    store.init()
    ok = False
    try:
        total = AtomicIndexStats()
        for s in opts.sources:
            st = index_source(store, IndexSource(root=s.id, dir=s.dir), eff_opts)
            total.scanned += st.scanned
            total.changed += st.changed
            total.deleted += st.deleted
            total.chunks += st.chunks
            total.parse_failures += st.parse_failures
            total.read_failures += st.read_failures
            if st.missing:
                total.missing_roots.append(s.id)
        # Ghost-root sweep: a root that indexed before but is NOT part of this
        # run (dropped from config, dir renamed away) would otherwise keep its
        # rows forever — every search keeps serving them with no signal. Only
        # a FULL run sweeps: an explicit-source run names a subset ON PURPOSE
        # and must not touch the others.
        if preexisting and not opts.explicit:
            keep = {s.id for s in opts.sources}
            for root in store.roots():
                if root not in keep:
                    store.delete_by_root(root)
                    total.swept_roots.append(root)
        # Read counts from the still-open store so callers never need a second
        # connection just to report them.
        counts = store.counts()
        # Stamp the schema version + config hashes so the gates are satisfied
        # next open. The design adds the SQLite + schema versions to kb_meta.
        store.set_user_version(SCHEMA_VERSION)
        store.set_meta("schema_version", str(SCHEMA_VERSION))
        store.set_meta("sqlite_version", sqlite3.sqlite_version)
        if opts.facet_config_hash is not None:
            store.set_meta("facetConfigHash", opts.facet_config_hash)
        if opts.stored_row_config_hash is not None:
            store.set_meta("storedRowConfigHash", opts.stored_row_config_hash)
        if preexisting:
            store.close()
        else:
            store.finalize_rename(db_path)
        ok = True
        return {"scanned": total.scanned, "changed": total.changed, "deleted": total.deleted, "chunks": total.chunks,
                "parse_failures": total.parse_failures, "read_failures": total.read_failures,
                "missing_roots": total.missing_roots, "swept_roots": total.swept_roots, "counts": counts}
    finally:
        if not ok:
            # Only a run that CREATED the file cleans it up; an existing valid
            # DB is left in place (valid & queryable).
            if preexisting:
                try:
                    store.close()
                except sqlite3.Error:
                    pass
            else:
                store.close_and_unlink()


def _normalize_link(w: str) -> str:
    """[[name]] → basename match: resolve to "<name>.md" leaf."""
    name = w.split("|")[0].split("#")[0].strip()
    return name if name.endswith(".md") else f"{name}.md"


def _normalize_rel(from_path: str, link: str) -> str:
    dir = from_path.rsplit("/", 1)[0] if "/" in from_path else ""
    parts = (dir + "/" if dir else "") + link
    stack: list = []
    for seg in parts.split("/"):
        if seg in (".", ""):
            continue
        if seg == "..":
            if stack:
                stack.pop()
        else:
            stack.append(seg)
    return "/".join(stack)
