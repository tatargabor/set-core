"""Score markers, thresholds and the digest.

The score is read ONLY from a whole-line `<!-- <marker>:score k=v ... -->` comment outside
fenced code blocks. A marker that is missing, malformed, short a dimension or out of range
makes the item UNSCORED — never a zero, because a zero is a verdict and a parse failure is
not one.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .declaration import Declaration, Rubric
from .items import Item, items

logger = logging.getLogger(__name__)

FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Score:
    values: Optional[Dict[str, int]]
    problem: str = ""

    @property
    def total(self) -> Optional[int]:
        return sum(self.values.values()) if self.values is not None else None


def _lines_outside_fences(text: str):
    inside = False
    for line in text.splitlines():
        if FENCE.match(line):
            inside = not inside
            continue
        if not inside:
            yield line


def parse_score(text: str, rubric: Rubric) -> Score:
    pat = re.compile(rf"^\s*<!--\s*{re.escape(rubric.marker)}:score\s+(.*?)\s*-->\s*$")
    found = [m for m in (pat.match(line) for line in _lines_outside_fences(text)) if m]
    if not found:
        return Score(None, "no score marker")
    if len(found) > 1:
        return Score(None, "more than one score marker")
    body = found[0].group(1)
    pairs = re.findall(r"(\w+)=(\S+)", body)
    if not pairs or re.sub(r"\w+=\S+", "", body).strip():
        return Score(None, "malformed score marker")
    kv = dict(pairs)
    values = {}
    for d in rubric.dimensions:
        if d.key not in kv:
            return Score(None, f"dimension '{d.key}' missing")
        if not re.fullmatch(r"\d+", kv[d.key]):
            return Score(None, f"dimension '{d.key}' is not an integer: {kv[d.key]!r}")
        v = int(kv[d.key])
        if v > d.max:
            return Score(None, f"dimension '{d.key}' = {v} is above its maximum {d.max}")
        values[d.key] = v
    extra = set(kv) - {d.key for d in rubric.dimensions}
    if extra:
        return Score(None, f"unknown dimension(s) {sorted(extra)}")
    return Score(values)


def qualifies(score: Score, rubric: Rubric) -> bool:
    if score.values is None:
        return False
    if score.total < rubric.total_min:
        return False
    return all(score.values[k] >= m for k, m in rubric.dimension_min.items())


@dataclass
class DigestRow:
    item: Item
    score: Score
    qualifies: bool
    has_draft: bool


def digest_rows(decl: Declaration, date: Optional[str]) -> List[DigestRow]:
    rubric = decl.require_rubric()
    rows = []
    for it in items(decl):
        if date is not None and it.collected != date:
            continue
        s = parse_score(it.text, rubric)
        rows.append(DigestRow(it, s, qualifies(s, rubric), it.draft_path(decl.drafts.suffix).exists()))
    rows.sort(key=lambda r: (-(r.score.total if r.score.total is not None else -1), r.item.path.name))
    return rows


def warnings(rows: List[DigestRow]) -> List[str]:
    out = [f"unscored: {r.item.path.name} ({r.score.problem})" for r in rows if r.score.values is None]
    out += [f"qualifies but has no draft: {r.item.path.name}" for r in rows if r.qualifies and not r.has_draft]
    return out


def render_digest(decl: Declaration, date: str, rows: List[DigestRow], all_items: bool) -> str:
    rubric = decl.require_rubric()
    th = f"total ≥ {rubric.total_min}/{rubric.total_max}"
    if rubric.dimension_min:
        th += "".join(f" and {next(d.label for d in rubric.dimensions if d.key == k)} ≥ {m}"
                      for k, m in rubric.dimension_min.items())
    dims = " · ".join(d.label for d in rubric.dimensions)
    lines = [
        f"# Feed digest, {date}",
        "",
        f"- Sources: {', '.join(f'{s.id} ({s.url})' for s in decl.sources)}",
        f"- Items: {len(rows)} ({'all collected' if all_items else 'collected on this day'})",
        f"- Threshold: {th}",
        f"- Dimensions: {dims}",
        "- Nothing is posted or sent by the system; a human decides and sends.",
        "",
    ]
    warns = warnings(rows)
    if warns:
        lines += [f"- WARNING: {w}" for w in warns] + [""]
    lines += [f"| # | score | {dims} | reply? | item | {decl.labels.reason} | draft |",
              "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        s = r.score
        total = f"{s.total}/{rubric.total_max}" if s.values is not None else "unscored"
        parts = " · ".join(str(s.values[d.key]) for d in rubric.dimensions) if s.values is not None else "-"
        draft = r.item.draft_path(decl.drafts.suffix)
        dcell = f"[draft]({draft.name})" if r.has_draft else ("**missing!**" if r.qualifies else "below threshold")
        lines.append(f"| {i} | {total} | {parts} | {'**yes**' if r.qualifies else 'no'} | "
                     f"[{r.item.title}]({r.item.path.name}) | {r.item.reason or '-'} | {dcell} |")
    lines += ["", f"Generated: `set-feed-watch digest {date}{' --all' if all_items else ''}`", ""]
    return "\n".join(lines)
