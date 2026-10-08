# Ported from an MIT-licensed upstream retrieval engine — see LICENSE-UPSTREAM in this package for the notice, the upstream commit and the port lineage.
"""Minimal glob → regex (supports ``**``, ``*``, ``?``) for include/exclude.

The channel classifier uses the SAME glob semantics the include/exclude
filtering uses — a second implementation is exactly how a pattern starts
matching in one place and not in the other. One implementation, two callers.

The patterns are matched against the ROOT-RELATIVE path: a repo-anchored
`**/inputs/copilot/**` silently does NOT fire under a `docs/inputs` root,
where the relative path is `copilot/2026-08/…`.

Two shapes are normalised that used to compile into patterns that can never
match a root-relative path — a silent full un-exclusion:

- a trailing `/` (dir-style `copilot/`) compiled to `…/$`, which no FILE path
  ends with → the whole tree flowed back INTO the index;
- a leading `./` compiled to an escaped literal prefix, which no root-relative
  path starts with → same silent no-fire.

A trailing slash is re-written as "this directory and everything under it"
(``copilot/`` ≡ ``copilot/**``).
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Pattern

logger = logging.getLogger(__name__)

_GS = "«GS»"
_G = "«G»"


def glob_to_re(pattern: str) -> Pattern[str]:
    dir_style = bool(re.search(r"/+$", pattern))
    g = re.sub(r"/+$", "", re.sub(r"^\./", "", pattern)) + ("/**" if dir_style else "")
    body = (
        re.sub(r"[.+^$(){}|\\]", lambda m: "\\" + m.group(0), g)
        .replace("**/", _GS)
        .replace("**", _G)
        .replace("*", "[^/]*")
        .replace("?", "[^/]")
        .replace(_GS, "(.*/)?")
        .replace(_G, ".*")
    )
    return re.compile("(^|/)" + body + "$")


def match_any(pats: Iterable[Pattern[str]], rel: str) -> bool:
    return any(p.search(rel) for p in pats)
