"""Item files: one Markdown file per collected item, and dedupe over them.

The text hash is deliberately the first version's algorithm, unchanged — SHA-1 over the
lower-cased, whitespace-collapsed verbatim body, first 12 hex digits — so items written
before this module existed hash identically. A test pins it.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .adapters import any_item_id
from .declaration import Declaration

logger = logging.getLogger(__name__)

ITEM_GLOB = "20??-??-??-*.md"


def text_hash(body: str) -> str:
    norm = re.sub(r"\s+", " ", body).strip().lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


def body_of(text: str, score_heading: str) -> str:
    """The verbatim item text: between the first two lines that are exactly '---'.

    A file with no closing '---' ends at the scoring heading instead.
    """
    lines = text.splitlines()
    marks = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if not marks:
        return ""
    end = marks[1] if len(marks) > 1 else len(lines)
    for i in range(marks[0] + 1, end):
        if lines[i].startswith(score_heading):
            end = i
            break
    return "\n".join(lines[marks[0] + 1:end])


def header_field(text: str, label: str) -> str:
    m = re.search(rf"^- {re.escape(label)}:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


@dataclass
class Item:
    path: Path
    title: str
    link: str
    id: str
    hash: str
    reason: str
    collected: str
    text: str

    def draft_path(self, suffix: str) -> Path:
        return self.path.with_name(self.path.stem + suffix + ".md")


def _is_item_file(p: Path, decl: Declaration) -> bool:
    if p.stem.endswith(decl.drafts.suffix):
        return False
    digest_tail = decl.digest_filename.split("{date}", 1)[1]
    if digest_tail and p.name.endswith(digest_tail):
        return False
    return True


def item_files(decl: Declaration) -> List[Path]:
    if not decl.dir.is_dir():
        logger.warning("feed-watch items dir does not exist: %s", decl.dir)
        return []
    return sorted(p for p in decl.dir.glob(ITEM_GLOB) if _is_item_file(p, decl))


def parse_item(path: Path, decl: Declaration) -> Item:
    text = path.read_text(encoding="utf-8")
    lab = decl.labels
    title = text.splitlines()[0].lstrip("# ").strip() if text else path.stem
    link = header_field(text, lab.link)
    reason = header_field(text, lab.reason)
    collected = re.search(r"\d{4}-\d{2}-\d{2}", header_field(text, lab.collected))
    return Item(path=path, title=title, link=link, id=any_item_id(link),
                hash=text_hash(body_of(text, lab.score_heading)), reason=reason,
                collected=collected.group(0) if collected else path.name[:10], text=text)


def items(decl: Declaration) -> List[Item]:
    return [parse_item(p, decl) for p in item_files(decl)]


def find_known(decl: Declaration, body: str, link: str) -> Optional[Item]:
    """The stored item this one duplicates, by source id first, then by text hash."""
    h, iid = text_hash(body), any_item_id(link)
    for it in items(decl):
        if (iid and it.id == iid) or (body.strip() and it.hash == h):
            return it
    return None
