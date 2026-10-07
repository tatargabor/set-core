"""`get` --section resolution.

The search page renders only the LEAF heading, while a store match on
heading_path is EXACT. A caller pasting the leaf from the page therefore got a
"not found" that blamed a path which was in the index, for what was a section
mismatch.

Resolution order: exact full headingPath first (the pre-fix behaviour,
unchanged), then the leaf. An ambiguous leaf (same leaf under two parents)
names its full paths instead of guessing. A found section returns ALL slices:
the chunker splits a >4000-char section into consecutive slices sharing one
headingPath, and a single-slice limit silently truncated such a section.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from set_kb.types import Chunk

logger = logging.getLogger(__name__)


@dataclass
class SectionResolution:
    kind: str  # "found" | "ambiguous" | "missing"
    slices: Optional[list] = None  # for "found": ALL chunks of the section
    candidates: Optional[list] = None  # for "ambiguous": the full heading paths


def leaf_of(heading_path: str) -> str:
    """Last breadcrumb segment — mirrors the render's leaf heading."""
    parts = heading_path.split(" > ")
    return parts[-1] or heading_path


def resolve_section(chunks: list, section: str) -> SectionResolution:
    wanted = section.strip()
    if not wanted:
        return SectionResolution(kind="missing")

    exact = [c for c in chunks if c.heading_path == wanted]
    if exact:
        return SectionResolution(kind="found", slices=exact)

    # Leaf match, grouped by full headingPath: one group → that whole section;
    # several → ambiguous (the caller must say WHICH "Background" it means).
    by_path: dict = {}
    for c in chunks:
        if leaf_of(c.heading_path) != wanted:
            continue
        by_path.setdefault(c.heading_path, []).append(c)
    if len(by_path) == 1:
        return SectionResolution(kind="found", slices=next(iter(by_path.values())))
    if len(by_path) > 1:
        return SectionResolution(kind="ambiguous", candidates=list(by_path.keys()))
    return SectionResolution(kind="missing")
