"""Scope capture from the path (design D9 of the change).

A scope rule is `{"name": "client", "pattern": "docs/clients/{scope}/**"}`:
at index time the `{scope}` placeholder captures the value from the file's
path, and the captured value is stored per chunk. A search restricted with
`--scope client=<value>` then returns only sources carrying that value —
within one repository, one client's material without another's on the page.

The stored form is the composite `"<name>=<value>"`, which is the exact
string the filter matches and the hit carries. One column, no join, and
several named scopes cannot collide.

Patterns are matched against the ROOT-RELATIVE path — the same anchoring the
exclusion patterns and the channel rules use. In the default corpus the only
root is the repository root, so root-relative and repo-relative coincide
there; a multi-root project writes its patterns the way its roots lay the
paths out.

Validation lives with the configuration loader (`config`), which reports the
offending key path; this module compiles and captures. The compile-time check
duplicates the loader's on purpose — a pattern that lost its placeholder must
never compile into a regex that silently captures nothing.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

PLACEHOLDER = "{scope}"


@dataclass
class ScopeRule:
    """One scope rule: `name` labels the captured value, `pattern` is a glob
    over the root-relative path holding `{scope}` exactly once."""

    name: str
    pattern: str


def check_pattern(pattern: str) -> None:
    """Raise unless the pattern carries `{scope}` exactly once — the loader
    reports the key path; this names the pattern itself."""
    if not isinstance(pattern, str) or PLACEHOLDER not in pattern:
        raise ValueError(f"kb scope: pattern {pattern!r} does not contain {{scope}} — nothing could be captured")
    if pattern.count(PLACEHOLDER) > 1:
        raise ValueError(f"kb scope: pattern {pattern!r} contains more than one {{scope}}")


def _fragment(frag: str) -> str:
    """Glob-translate one placeholder-free fragment (`**`, `*`, `?`). The
    `**` forms go through placeholder tokens, exactly like `glob.glob_to_re`:
    expanding `**` to `.*` before `*` is translated would let the second
    replace re-write the star INSIDE the `.*` it just produced."""
    _GS, _G = "«GS»", "«G»"
    out = re.sub(r"[.+^$(){}|\[\]\\]", lambda m: "\\" + m.group(0), frag)
    return (
        out.replace("**/", _GS)
        .replace("**", _G)
        .replace("*", "[^/]*")
        .replace("?", "[^/]")
        .replace(_GS, "(?:.*/)?")
        .replace(_G, ".*")
    )


def compile_scope_rules(rules: Optional[Sequence[ScopeRule]]):
    """Compile once per index run. Returns `[(rule, regex), ...]` in
    configuration order — the FIRST rule whose pattern matches decides the
    scope, so ordering is meaningful exactly like the channel rules."""
    out = []
    for r in rules or []:
        check_pattern(r.pattern)
        head, _, tail = r.pattern.partition(PLACEHOLDER)
        out.append((r, re.compile("^" + _fragment(head) + "([^/]+)" + _fragment(tail) + "$")))
    return out


def capture_scope(compiled, rel_path: str) -> Optional[str]:
    """The captured `"<name>=<value>"` for one root-relative path, or None
    when no rule matches. None is a real answer — the file lives outside every
    declared scope — not a claim that it is unscoped by mistake."""
    for rule, rx in compiled:
        m = rx.match(rel_path)
        if m:
            return f"{rule.name}={m.group(1)}"
    return None
