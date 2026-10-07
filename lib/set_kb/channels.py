"""Channel classification of sources by root-scoped rules.

WHY A CHANNEL AT ALL. A small layer of a corpus (the client's own voice —
mails, meeting transcripts, chat) is buried by BM25 length normalisation, and
the root PRIORITY does not help: priority decides the dedup winner, never the
rank. The reserved lane (see `search`) therefore needs a field of its own, and
this module computes it.

THE RULE IS ROOT-SCOPED, AND THAT IS ENFORCED AT CONFIG VALIDATION, NOT
ADVISED HERE. During the originating measurement a single path pattern
classified an internal ticket about a client report as the CLIENT channel —
it is the project's own ticket ABOUT the report, not the report. A rule
therefore names its `roots`, and the configuration loader rejects a rule
without them. A path pattern alone is the measured bug. (The rejection lives
with config validation, wave W2; this module compiles and applies rules.)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Pattern, Sequence

from set_kb.glob import glob_to_re, match_any

logger = logging.getLogger(__name__)


@dataclass
class ChannelRule:
    """One channel rule.

    `roots` is mandatory (see above); `include` narrows within those roots,
    `exclude` vetoes. Patterns are ROOT-RELATIVE, the same anchoring the
    indexer's include/exclude uses.
    """

    channel: str
    roots: Sequence[str]
    include: Optional[Sequence[str]] = None  # omitted = the whole root belongs
    exclude: Optional[Sequence[str]] = None  # vetoes even when include matched


@dataclass
class CompiledRule:
    channel: str
    roots: frozenset
    include: Optional[list]
    exclude: Optional[list]


def compile_channel_rules(rules: Optional[Sequence[ChannelRule]]):
    """Compile once per index/search run — glob compilation is not free per file."""
    return [
        CompiledRule(
            channel=r.channel,
            roots=frozenset(r.roots or ()),
            include=[glob_to_re(p) for p in r.include] if r.include else None,
            exclude=[glob_to_re(p) for p in r.exclude] if r.exclude else None,
        )
        for r in (rules or [])
    ]


def classify_channel(rules, root: str, rel_path: str) -> Optional[str]:
    """Channel of one file, or `None` when no rule claims it.

    FIRST MATCH WINS, so ordering in the configuration is meaningful: put the
    narrow rule before the broad one. `None` is a real answer — "the
    configuration classifies this file into no channel" — and NOT a claim that
    the file is uninteresting.
    """
    for r in rules:
        if root not in r.roots:
            continue
        if r.exclude and match_any(r.exclude, rel_path):
            continue
        if r.include and not match_any(r.include, rel_path):
            continue
        return r.channel
    return None
