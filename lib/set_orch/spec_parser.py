"""Spec entity-reference parser (`design-binding-completeness`).

Spec.md and linked feature spec files use inline markers to bind to design
entities:
  @component:NAME    — references a shell component (matches manifest.shared)
  @route:/PATH       — references a manifest route

The parser extracts these markers; the validator checks them against a
loaded `Manifest`. Decompose populates per-change `design_components` from
extracted markers; write-spec lint warns when a UI feature has no markers.

Design intent: keep spec.md FUNCTIONAL (WHAT) and let the design source
own the visual (HOW). Markers are the only place spec.md mentions design
entities — the entity name is enough; concrete TSX paths are resolved at
decompose time via the manifest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .design_manifest import Manifest


# ─── Marker syntax ─────────────────────────────────────────────────


# Names: kebab-case, lowercase, ≥1 alpha then alnum/dash. Avoids matching
# email-like patterns (`@user:domain` etc.).
_COMPONENT_RE = re.compile(r"@component:([a-z][a-z0-9-]+)")
# Route paths: start with /, then any non-whitespace.
_ROUTE_RE = re.compile(r"@route:(/\S+)")


@dataclass
class EntityRef:
    """A single entity reference extracted from spec text."""

    kind: Literal["component", "route"]
    name: str  # for component: kebab-case identifier; for route: path string
    line: int  # 1-based line number where the marker appears
    raw: str  # full marker text (e.g. "@component:search-palette")


@dataclass
class ValidationError:
    """A reference that does not resolve to a manifest entry."""

    ref: EntityRef
    reason: str  # human-readable explanation
    suggestions: list[str]  # closest matches from manifest


# ─── Extraction ────────────────────────────────────────────────────


_COMBINED_RE = re.compile(
    r"@(?P<kind>component|route):(?P<name>(?:[a-z][a-z0-9-]+|/\S+))"
)


def extract_design_references(spec_text: str) -> list[EntityRef]:
    """Extract `@component:` and `@route:` markers from spec text.

    Returns refs in document order (preserving within-line ordering).
    Duplicates are kept (caller dedupes via `resolve_*_paths`).
    """
    refs: list[EntityRef] = []
    for m in _COMBINED_RE.finditer(spec_text):
        kind = m.group("kind")
        name = m.group("name")
        # Strip trailing punctuation that grabbed onto the regex (routes only)
        if kind == "route":
            name = name.rstrip(".,;:!?)")
        line = spec_text.count("\n", 0, m.start()) + 1
        refs.append(EntityRef(
            kind=kind,
            name=name,
            line=line,
            raw=f"@{kind}:{name}",
        ))
    return refs


# ─── Validation ────────────────────────────────────────────────────


def validate_references(
    refs: list[EntityRef],
    manifest: "Manifest",
) -> list[ValidationError]:
    """Validate each reference resolves to a manifest entry.

    Args:
        refs: References extracted by `extract_design_references`.
        manifest: The loaded `Manifest`.

    Returns:
        List of `ValidationError`s (one per unresolved reference). Empty
        list means all references are valid.
    """
    errors: list[ValidationError] = []

    # Build lookup sets
    shell_basenames = {
        _basename(p): p for p in manifest.shared
        if p.endswith(".tsx")
    }
    known_routes = {r.path for r in manifest.routes}

    for ref in refs:
        if ref.kind == "component":
            if ref.name in shell_basenames:
                continue
            # Suggest closest matches from shell list
            suggestions = _closest_matches(ref.name, list(shell_basenames.keys()))
            errors.append(ValidationError(
                ref=ref,
                reason=f"Component `{ref.name}` not found in manifest.shared",
                suggestions=suggestions,
            ))
        elif ref.kind == "route":
            if ref.name in known_routes:
                continue
            # Try prefix match for dynamic routes (e.g. /kavek/[slug] vs /kavek/abc)
            base = ref.name.split("/[")[0]
            prefix_hit = any(
                kr.split("/[")[0] == base for kr in known_routes if "[" in kr
            )
            if prefix_hit:
                continue
            suggestions = _closest_matches(ref.name, list(known_routes))
            errors.append(ValidationError(
                ref=ref,
                reason=f"Route `{ref.name}` not found in manifest.routes",
                suggestions=suggestions,
            ))

    return errors


def _basename(path: str) -> str:
    """v0-export/components/site-header.tsx → site-header"""
    p = path.rstrip("/")
    seg = p.rsplit("/", 1)[-1]
    if seg.endswith(".tsx"):
        seg = seg[:-4]
    return seg


def _closest_matches(needle: str, haystack: list[str], limit: int = 3) -> list[str]:
    """Return up to `limit` closest matches by Levenshtein distance."""
    if not haystack:
        return []
    scored = sorted(haystack, key=lambda s: _lev(s, needle))
    return scored[:limit]


def _lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    m = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        m[i][0] = i
    for j in range(len(b) + 1):
        m[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            m[i][j] = min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + cost)
    return m[len(a)][len(b)]


# ─── Helpers for callers ────────────────────────────────────────────


def resolve_component_paths(
    refs: list[EntityRef],
    manifest: "Manifest",
) -> list[str]:
    """Return the manifest-relative TSX paths for `@component:` refs.

    Skips unresolved refs (use `validate_references` for the error list).
    Routes (`@route:`) are NOT included — they belong to `design_routes`.
    """
    shell_basenames = {
        _basename(p): p for p in manifest.shared
        if p.endswith(".tsx")
    }
    out: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref.kind != "component":
            continue
        path = shell_basenames.get(ref.name)
        if path and path not in seen:
            out.append(path)
            seen.add(path)
    return out


def resolve_route_paths(refs: list[EntityRef]) -> list[str]:
    """Return route paths for `@route:` refs, deduplicated."""
    out: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref.kind != "route":
            continue
        if ref.name not in seen:
            out.append(ref.name)
            seen.add(ref.name)
    return out
