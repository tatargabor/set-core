# Ported from an MIT-licensed upstream retrieval engine — see LICENSE-UPSTREAM in this package for the notice, the upstream commit and the port lineage.
"""The swappable language seam.

A pack carries:

- ``stopwords`` — function words dropped from the QUERY tokens, so they do not
  drive the ranking. Always present.
- ``stem`` — OPTIONAL, and no shipped pack fills it: a stemmer whose output
  disagreed with what FTS5 indexed would silently lose matches rather than
  error, and the measurement found no benefit. The seam exists because the
  PLACE is needed, not because we have content for it.

Divergence from upstream: upstream has no language seam at all — a single
module-level set of English words lives inside its store and every
tokenization reads it. This module lifts that set behind the pack.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Optional

logger = logging.getLogger(__name__)


@dataclass
class LanguagePack:
    """The swappable language seam. The engine runs without one."""

    id: str
    stopwords: frozenset
    stem: Optional[Callable[[str], str]] = None


# Upstream's English function words — verbatim, so the port keeps its ranking
# behaviour when no pack is selected.
ENGLISH_STOPWORDS = frozenset(
    "the for and how what with you your does can from that this are into use using get set all a an of to in on is be as it or by at do".split(" ")
)

english_pack = LanguagePack(id="en", stopwords=frozenset(ENGLISH_STOPWORDS))

_REGISTRY: Dict[str, LanguagePack] = {english_pack.id: english_pack}


def register_language_pack(pack: LanguagePack) -> None:
    """Register a pack (or replace one) under its id."""
    _REGISTRY[pack.id] = pack


def language_pack(id: str) -> LanguagePack:
    """Resolve a pack by id. An unknown id RAISES rather than falling back: a
    typo in `language` would otherwise silently ship English stopwords over a
    corpus in another language, and nothing on the result page would say so."""
    p = _REGISTRY.get(id)
    if p is None:
        raise KeyError(f"kb: unknown language pack {id!r} (known: {', '.join(sorted(_REGISTRY))})")
    return p


def registered_languages() -> Iterable[str]:
    return sorted(_REGISTRY)
