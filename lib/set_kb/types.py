# Ported from an MIT-licensed upstream retrieval engine — see LICENSE-UPSTREAM in this package for the notice, the upstream commit and the port lineage.
"""Core types of the knowledge-base engine.

Storage is reached only through the store module — the chunker, indexer and
searcher never issue SQL themselves — so a different backend is a swap, not a
rewrite.

Divergences from the intermediate TypeScript port this module ports: the DOX /
trust-machinery types (verdict labels, hit verdicts) are not carried — they
were dropped upstream-side already and set-core never computes them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

DOC_TYPES = ("doc", "agents", "source-md")
DocType = str  # one of DOC_TYPES


@dataclass
class Chunk:
    """A structural (heading) chunk of a markdown file."""

    root: str  # configured source root id (relative or label)
    path: str  # path relative to its root, portable (POSIX separators, NFC)
    chunk_id: str  # stable id within file ("&lt;sha8&gt;:&lt;ordinal&gt;")
    heading_path: str  # breadcrumb: "A > B > C"
    heading: str  # leaf heading
    level: int  # 0 = preamble/file, 1..6 = ATX depth
    parent_chunk_id: Optional[str]
    doc_type: DocType
    body: str  # section text (breadcrumb is indexed via columns, not prepended)
    body_hash: str  # sha256 of trimmed body (exact-content dedup)
    # Source channel. Classified from the root AND the path by configuration,
    # never in code. None = the configuration classifies this file into no
    # channel.
    channel: Optional[str] = None
    # Scope captured from the path at index time (design D9), stored as
    # "<name>=<value>" — the exact string `--scope` filters on. None = the file
    # matched no scope pattern.
    scope: Optional[str] = None
    # Further sections of this file NOT returned by a path-only fetch, so a
    # fetch can never silently truncate a multi-chunk file. None/0 = this is
    # the whole story.
    suppressed_sections: Optional[int] = None


@dataclass
class FileState:
    mtime_ms: float
    # Byte size — compared alongside mtime in the incremental cheap-check, so a
    # mtime-preserving content swap is re-hashed instead of skipped forever.
    size: int
    sha256: str


@dataclass
class GraphNode:
    type: str  # "file" | "heading" | "tag" | "entity"
    name: str  # canonical label (heading_path for headings, path for files)
    path: Optional[str]


@dataclass
class GraphEdge:
    src: str
    dst: str
    rel: str  # "child_of" | "links_to" | "references" | "has_tag"
    weight: float = 1.0


@dataclass
class PropertyRow:
    """A property row persisted for a file's facet frontmatter."""

    root: str
    path: str
    key: str
    value: str  # normalized (lowercased/trimmed)
    value_num: Optional[float] = None
    value_date: Optional[str] = None
    value_raw: str = ""


@dataclass
class Filter:
    """Structured frontmatter facet filter. Values are always parameter-bound."""

    key: str
    op: str  # "eq" | "in" | "gte" | "lte"
    value: object = None
    values: Optional[Sequence[object]] = None
    type: Optional[str] = None  # "string" | "number" | "date"


@dataclass
class KbHit:
    root: str
    path: str
    heading_path: str
    chunk_id: str
    doc_type: DocType
    score: float  # lower = more relevant (BM25 convention)
    snippet: str
    # Internal: the chunk this hit was rendered from, for the parent expansion.
    # Never serialized.
    _parent_chunk_id: Optional[str] = field(default=None, repr=False)
    # Duplicate copies collapsed by exact-content dedup. Absent = no duplicate.
    aka_paths: Optional[list[str]] = None
    # Further matching sections of this same source collapsed by source-level
    # dedup. 0 = this source matched exactly once.
    suppressed_sections: Optional[int] = None
    # Small-to-big parent context. Display-only, NOT a refetch key.
    parent: Optional[dict] = None
    # Source channel of the hit; None = classified into no channel.
    channel: Optional[str] = None
    # Scope of the hit ("<name>=<value>"); None = the file matched no scope
    # pattern at index time.
    scope: Optional[str] = None

    def to_json_dict(self) -> dict:
        """The oracle/CLI field set: the reference engine's hit keys, camelCase.

        Absent optional fields are omitted (as the reference JSON omits them);
        `suppressedSections` is always present once source dedup ran, `channel`
        and `scope` are always present (null when unclassified / uncaptured —
        the JSON contract names both per hit)."""
        out: dict = {
            "root": self.root,
            "path": self.path,
            "headingPath": self.heading_path,
            "chunkId": self.chunk_id,
            "docType": self.doc_type,
            "channel": self.channel,
            "scope": self.scope,
            "score": self.score,
            "snippet": self.snippet,
        }
        if self.aka_paths is not None:
            out["akaPaths"] = self.aka_paths
        if self.suppressed_sections is not None:
            out["suppressedSections"] = self.suppressed_sections
        if self.parent is not None:
            out["parent"] = self.parent
        return out


@dataclass
class SearchOpts:
    """Ranking options. Defaults mirror the reference engine's own fallbacks."""

    limit: int = 10
    root: Optional[str] = None
    doc_type: Optional[DocType] = None
    dedup: bool = True  # exact-content collapse
    source_dedup: bool = True  # collapse to one hit per (root, path)
    # Share of the result page reserved for the lane channels (0..1). 0
    # disables the lane quota. Ignored when doc_type is set.
    lane_quota: float = 0.5
    # Relative score margin (0..1) letting the reserved lane take slot 1 when
    # `r0 - m0 <= margin * |m0|` on raw BM25(+proximity) scores. 0 = off.
    lane_lead_margin: float = 0.0
    # IDF-weighted coverage rerank. Opt-IN: measured a net regression upstream.
    coverage_rerank: bool = False
    field_weights: Optional[dict] = None  # {heading_path, heading, body}
    root_priority: Optional[dict] = None  # root id -> priority (dedup winner)
    proximity_boost: bool = False  # in-order/proximity aux ranker
    diversity: Optional[dict] = None  # {enabled: bool, lambda: float}
    expand_parent: bool = False  # attach parent section context
    # Channel values whose hits form the RESERVED lane. DIVERGENCE (design D8):
    # an EMPTY set means NO reserved lane here — the reference falls back to a
    # lane for agent-instruction files, which on a project corpus would reserve
    # the page for CLAUDE.md-type files.
    lane_channels: Sequence[str] = ()
    # Path fragments whose hits are excluded, matched against `root/path`.
    # Applied in the SQL WHERE, never as a post-filter: a post-filter would
    # shrink the page BELOW `limit` instead of letting the next hit take the
    # freed slot.
    exclude_paths: Sequence[str] = ()
    query_expansion: str = "off"  # "off" | "prf" | "synonym" | "agent"
    synonyms: Optional[dict] = None  # curated glossary for synonym expansion
    prf: Optional[dict] = None  # {terms, topK, dfCeiling}
    filters: Optional[Sequence[Filter]] = None
    language: Optional[object] = None  # a LanguagePack; None = English pack
    # Cross-encoder rerank hook: no-op without an injected callable.
    rerank: bool = False
    reranker: Optional[Callable] = None
    # Restrict the page to one captured scope, in the stored "<name>=<value>"
    # form. Applied in the SQL WHERE (see `_Clauses`): a post-filter would
    # shrink the page below `limit` instead of letting the next hit take the
    # freed slot.
    scope: Optional[str] = None


@dataclass
class SearchPage:
    """One rendered result page: the hits PLUS what the page is not showing."""

    hits: list
    # Distinct matching SOURCES under the active filters and exclusions, before
    # the limit and before the lane quota.
    total: int
    has_more: bool
    exclusions: list

    def to_json_dict(self) -> dict:
        return {
            "hits": [h.to_json_dict() for h in self.hits],
            "total": self.total,
            "hasMore": self.has_more,
            "exclusions": list(self.exclusions),
        }
