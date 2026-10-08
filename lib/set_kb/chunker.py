# Ported from an MIT-licensed upstream retrieval engine — see LICENSE-UPSTREAM in this package for the notice, the upstream commit and the port lineage.
"""Structural (heading) chunker — fence-safe, breadcrumb-aware.

Line-based with a fenced-code state machine. Every section gets a stable uid
that survives flush/merge/split; the parent is stored as a uid and resolved to
a final chunk index at the very end. DIVERGENCE FROM UPSTREAM: upstream wrote
the PRE-merge ordinal into parentChunkId while chunkId carries the POST-split
index, so on `# Title` (empty body) / `## A` / `## B` the section "A" became
its own parent and "B" pointed at its sibling.

⚠ String lengths are Python code-point counts; the reference counts UTF-16
units. They differ only beyond the BMP, which the corpus contract does not
carry.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Optional

from set_kb.frontmatter import parse_frontmatter
from set_kb.types import Chunk

logger = logging.getLogger(__name__)

MIN_CHUNK_CHARS = 100
MAX_CHUNK_CHARS = 4000

_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_MD_LINK_RE = re.compile(r"\]\(([^)]+\.mdx?)\)")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class ParseResult:
    chunks: list
    frontmatter: Optional[dict]
    wikilinks: list  # [[name]] targets found anywhere in the file
    md_links: list  # [text](path.md) relative targets
    parse_failed: bool  # frontmatter block present but a line did not parse


@dataclass
class _Section:
    """A raw section between flush and merge/split."""

    uid: int
    heading_path: str
    heading: str
    level: int
    parent_uid: Optional[int]
    body: str = ""


@dataclass
class _StackEntry:
    level: int
    title: str
    uid: int


def chunk_markdown(root: str, path: str, text: str, doc_type: str = "doc") -> ParseResult:
    """Chunk one markdown document into structural sections.

    `root`/`path` identify the file; `path` is relative to its root,
    POSIX-separated, NFC. `doc_type` is stamped on every chunk.
    """
    parsed = parse_frontmatter(text)
    body_text, fm, parse_failed = parsed.body, parsed.fm, parsed.parse_failed
    lines = body_text.split("\n")
    file_title = re.sub(r"\.(md|mdx|markdown)$", "", path.rsplit("/", 1)[-1], flags=re.IGNORECASE)

    raw: list[_Section] = []
    stack: list[_StackEntry] = []
    # Parent of EVERY section, including those flush() drops for an empty body
    # — without this the ancestor walk below could not step over a dropped
    # heading.
    section_parent: dict[int, Optional[int]] = {}
    cur: Optional[_Section] = None
    in_fence = False
    fence_ch = ""
    next_uid = 0

    def flush() -> None:
        nonlocal cur
        if cur is not None and cur.body.strip():
            raw.append(cur)
            cur = None

    for line in lines:
        t = line.lstrip()
        fm2 = _FENCE_RE.match(t)
        if fm2:
            if not in_fence:
                in_fence = True
                fence_ch = fm2.group(1)[0]
            elif t.startswith(fence_ch):
                in_fence = False
            if cur is not None:
                cur.body += line + "\n"
            continue
        hm = None if in_fence else _HEADING_RE.match(line)
        if hm:
            flush()
            level = len(hm.group(1))
            title = hm.group(2).strip()
            while stack and stack[-1].level >= level:
                stack.pop()
            parent_uid = stack[-1].uid if stack else None
            uid = next_uid
            next_uid += 1
            section_parent[uid] = parent_uid
            stack.append(_StackEntry(level=level, title=title, uid=uid))
            cur = _Section(
                uid=uid,
                heading_path=" > ".join(s.title for s in stack),
                heading=title,
                level=level,
                parent_uid=parent_uid,
            )
        else:
            if cur is None:
                uid = next_uid
                next_uid += 1
                section_parent[uid] = None
                cur = _Section(uid=uid, heading_path=file_title, heading=file_title, level=0, parent_uid=None)
            cur.body += line + "\n"
    flush()

    # merge tiny chunks up into the previous
    merged: list[_Section] = []
    # uid -> uid of the section that swallowed it, so a child of a merged-away
    # section still resolves to the chunk its parent's text actually ended up in.
    absorbed_into: dict[int, int] = {}
    for c in raw:
        if len(c.body.strip()) < MIN_CHUNK_CHARS and merged:
            host = merged[-1]
            host.body += "\n" + c.heading + "\n" + c.body
            absorbed_into[c.uid] = host.uid
        else:
            merged.append(c)

    # split oversized leaf sections by paragraph
    sized: list[_Section] = []
    for c in merged:
        if len(c.body) <= MAX_CHUNK_CHARS:
            sized.append(c)
            continue
        buf = ""
        for p in re.split(r"\n\s*\n", c.body):
            if len(buf + p) > MAX_CHUNK_CHARS and buf:
                sized.append(_Section(c.uid, c.heading_path, c.heading, c.level, c.parent_uid, buf))
                buf = ""
            buf += p + "\n\n"
        if buf.strip():
            sized.append(_Section(c.uid, c.heading_path, c.heading, c.level, c.parent_uid, buf))

    prefix = _sha(path)[:8]

    # uid -> index of the FIRST chunk emitted for that section (a split section
    # owns several).
    uid_to_index: dict[int, int] = {}
    for i, c in enumerate(sized):
        if c.uid not in uid_to_index:
            uid_to_index[c.uid] = i

    # Walk up the ancestor chain until a section that actually produced a chunk
    # is found: a heading with an empty body is dropped by flush(), a tiny one
    # is merged into its host. Returns None when no ancestor survived — an
    # honest absence beats a wrong link.
    def resolve_parent(start: Optional[int], self_index: int) -> Optional[str]:
        uid = start
        seen: set[int] = set()
        while uid is not None and uid not in seen:
            seen.add(uid)
            idx = uid_to_index.get(absorbed_into.get(uid, uid))
            # A chunk is never its own parent — that was exactly the upstream symptom.
            if idx is not None and idx != self_index:
                return f"{prefix}:{idx}"
            uid = section_parent.get(uid)
        return None

    chunks = [
        Chunk(
            root=root,
            path=path,
            chunk_id=f"{prefix}:{i}",
            heading_path=c.heading_path,
            heading=c.heading,
            level=c.level,
            parent_chunk_id=resolve_parent(c.parent_uid, i),
            doc_type=doc_type,
            body=c.body.rstrip() if c.body else "",
            body_hash=_sha(c.body.strip()),
        )
        for i, c in enumerate(sized)
    ]

    wikilinks = [m.strip() for m in _WIKILINK_RE.findall(text)]
    md_links = [m.strip() for m in _MD_LINK_RE.findall(text)]

    return ParseResult(chunks=chunks, frontmatter=fm, wikilinks=wikilinks, md_links=md_links, parse_failed=parse_failed)
