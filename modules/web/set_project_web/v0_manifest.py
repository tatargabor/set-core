"""v0 design manifest: auto-generation, parsing, scope matching.

The manifest maps Next.js App Router routes + shared components to scope
keywords. Used by:
  - the fidelity gate for route inventory + skeleton check
  - WebProjectType.get_design_dispatch_context to generate focus-files
    hints in the dispatch markdown
  - WebProjectType.validate_plan_design_coverage for opt-in planner
    route-coverage enforcement

File format (YAML):

    design_source: v0
    v0_export_path: v0-export/

    routes:
      - path: /
        files: [v0-export/app/page.tsx]
        component_deps: [v0-export/components/hero.tsx]
        scope_keywords: [homepage, hero]
        fidelity_threshold: 1.5  # optional, per-route override

    shared:
      - v0-export/components/ui/**
      - v0-export/components/header.tsx
      - v0-export/app/layout.tsx
      - v0-export/app/globals.css

    shared_aliases: {}   # optional per-scaffold rename tolerance
    deferred_design_routes: []  # populated by planner, not importer
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import yaml

logger = logging.getLogger(__name__)

MANUAL_MARKER = "# manual"

# Files under v0-export/ that are always shared across routes.
SHARED_GLOBS = (
    "components/ui",
    "components/header.tsx",
    "components/footer.tsx",
    "components/site-header.tsx",
    "components/site-footer.tsx",
    "app/layout.tsx",
    "app/globals.css",
)

# Keywords that mark a change scope as UI-bound (drives hard-fail per AC-17b).
UI_KEYWORDS = (
    "page",
    "view",
    "component",
    "screen",
    "render",
    "layout",
    "form",
    "modal",
    "dialog",
)

IMPORT_RE = re.compile(
    r"""^\s*(?:import|export)\s+(?:[^'"]+?\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)


@dataclass
class RouteEntry:
    path: str
    files: list[str] = field(default_factory=list)
    component_deps: list[str] = field(default_factory=list)
    scope_keywords: list[str] = field(default_factory=list)
    fidelity_threshold: Optional[float] = None

    def to_dict(self) -> dict:
        d = {
            "path": self.path,
            "files": list(self.files),
            "component_deps": list(self.component_deps),
            "scope_keywords": list(self.scope_keywords),
        }
        if self.fidelity_threshold is not None:
            d["fidelity_threshold"] = self.fidelity_threshold
        return d


@dataclass
class Manifest:
    design_source: str = "v0"
    v0_export_path: str = "v0-export/"
    routes: list[RouteEntry] = field(default_factory=list)
    shared: list[str] = field(default_factory=list)
    shared_aliases: dict = field(default_factory=dict)
    deferred_design_routes: list[dict] = field(default_factory=list)

    def route_by_path(self, path: str) -> Optional[RouteEntry]:
        for r in self.routes:
            if r.path == path:
                return r
        return None

    def to_dict(self) -> dict:
        return {
            "design_source": self.design_source,
            "v0_export_path": self.v0_export_path,
            "routes": [r.to_dict() for r in self.routes],
            "shared": list(self.shared),
            "shared_aliases": dict(self.shared_aliases),
            "deferred_design_routes": list(self.deferred_design_routes),
        }


class ManifestError(RuntimeError):
    """Raised on manifest validation failure."""


class NoMatchingRouteError(RuntimeError):
    """Raised when UI-bound scope has no matching route in the manifest."""


# ─── Parsing ────────────────────────────────────────────────────────


def load_manifest(path: Path) -> Manifest:
    """Load and validate an existing manifest."""
    data = yaml.safe_load(path.read_text()) or {}
    m = Manifest(
        design_source=data.get("design_source", "v0"),
        v0_export_path=data.get("v0_export_path", "v0-export/"),
        shared=list(data.get("shared") or []),
        shared_aliases=dict(data.get("shared_aliases") or {}),
        deferred_design_routes=list(data.get("deferred_design_routes") or []),
    )
    for r in data.get("routes") or []:
        m.routes.append(
            RouteEntry(
                path=r["path"],
                files=list(r.get("files") or []),
                component_deps=list(r.get("component_deps") or []),
                scope_keywords=[k.lower() for k in (r.get("scope_keywords") or [])],
                fidelity_threshold=r.get("fidelity_threshold"),
            )
        )
    return m


# ─── Generation ─────────────────────────────────────────────────────


def generate_manifest_from_tree(
    v0_export_path: Path,
    manifest_path: Path,
) -> Manifest:
    """Auto-generate a manifest from a v0-export tree.

    - Scans app/**/page.tsx for routes
    - Derives URL segments into route paths
    - Traverses import graph one level to populate component_deps
    - Derives scope_keywords from URL segments + first H1 in page
    - Collects shared files (components/ui/**, layout.tsx, etc.)
    - Preserves lines marked '# manual' in any existing manifest file
    """
    v0_export_path = v0_export_path.resolve()
    app_dir = v0_export_path / "app"
    if not app_dir.is_dir():
        raise ManifestError(
            f"v0 export missing app/ directory at {app_dir} — cannot derive routes"
        )

    routes: list[RouteEntry] = []
    for page_file in sorted(app_dir.rglob("page.tsx")):
        route_path = _derive_route_path(page_file.relative_to(app_dir))
        rel_file = _rel_to_export(page_file, v0_export_path)
        deps = _collect_component_deps(page_file, v0_export_path)
        keywords = _derive_scope_keywords(page_file, route_path)
        routes.append(
            RouteEntry(
                path=route_path,
                files=[rel_file],
                component_deps=deps,
                scope_keywords=keywords,
            )
        )

    shared = _collect_shared_files(v0_export_path)

    existing_manual_lines: list[str] = []
    if manifest_path.is_file():
        existing_manual_lines = _extract_manual_lines(manifest_path)

    # Keep existing shared_aliases + deferred_design_routes (scaffold-authored).
    prev = None
    if manifest_path.is_file():
        try:
            prev = load_manifest(manifest_path)
        except Exception:
            logger.warning("existing manifest unparseable; will be overwritten", exc_info=True)

    m = Manifest(routes=routes, shared=shared)
    if prev is not None:
        m.shared_aliases = dict(prev.shared_aliases)
        m.deferred_design_routes = list(prev.deferred_design_routes)

    _report_scope_keyword_collisions(m)

    # Write YAML + preserve manual lines. allow_unicode=True keeps HU
    # accents (á, é, ő, ű, …) readable instead of \xE1-escaped.
    yaml_text = yaml.safe_dump(m.to_dict(), sort_keys=False, allow_unicode=True)
    if existing_manual_lines:
        yaml_text += "\n# Preserved manual overrides from previous manifest:\n"
        yaml_text += "\n".join(existing_manual_lines) + "\n"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(yaml_text)
    logger.info(
        "wrote design-manifest.yaml: %d routes, %d shared, %d manual-preserved",
        len(m.routes), len(m.shared), len(existing_manual_lines),
    )
    return m


def _derive_route_path(rel_page_path: Path) -> str:
    """Convert app/kavek/[slug]/page.tsx → /kavek/[slug]; app/page.tsx → /."""
    parts = list(rel_page_path.parts[:-1])  # drop "page.tsx"
    # Strip route groups (Next.js convention: (group))
    parts = [p for p in parts if not (p.startswith("(") and p.endswith(")"))]
    if not parts:
        return "/"
    return "/" + "/".join(parts)


def _collect_component_deps(page_file: Path, v0_root: Path) -> list[str]:
    """Return list of imported relative component paths, one level only."""
    try:
        text = page_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    deps: list[str] = []
    for m in IMPORT_RE.finditer(text):
        spec = m.group(1)
        if not (spec.startswith("@/") or spec.startswith("./") or spec.startswith("../")):
            continue
        resolved = _resolve_import(spec, page_file, v0_root)
        if resolved and resolved not in deps:
            deps.append(resolved)
    return deps


def _resolve_import(spec: str, from_file: Path, v0_root: Path) -> Optional[str]:
    """Resolve a TS/JS import spec to a relative path under v0-export/."""
    if spec.startswith("@/"):
        target_base = v0_root / spec[2:]
    else:
        target_base = (from_file.parent / spec).resolve()

    exts = (".tsx", ".ts", ".jsx", ".js")
    for ext in exts:
        candidate = target_base.with_suffix(ext) if target_base.suffix == "" else target_base
        if candidate.is_file():
            return _rel_to_export(candidate, v0_root)
        idx_candidate = Path(str(target_base)) / f"index{ext}"
        if idx_candidate.is_file():
            return _rel_to_export(idx_candidate, v0_root)
    return None


def _rel_to_export(path: Path, v0_root: Path) -> str:
    """Return path relative to scaffold root, prefixed with v0-export/."""
    rel = path.resolve().relative_to(v0_root.resolve())
    return f"{v0_root.name}/{rel.as_posix()}"


def _derive_scope_keywords(page_file: Path, route_path: str) -> list[str]:
    """Derive keywords from URL segments + first H1 in the page file."""
    kws: list[str] = []
    # URL segments (strip brackets for dynamic segments)
    for seg in route_path.strip("/").split("/"):
        if not seg:
            continue
        seg = seg.strip("[]")
        if seg:
            kws.append(_kebab(seg))
    # Homepage
    if route_path == "/":
        kws.append("homepage")
        kws.append("home")

    # First H1
    try:
        text = page_file.read_text(encoding="utf-8", errors="ignore")
        # Look for first <h1>TEXT</h1> — naive regex, trims JSX expressions
        m = re.search(r"<h1[^>]*>([^<{]+)</h1>", text)
        if m:
            headline = m.group(1).strip()
            for tok in re.split(r"\s+", headline.lower()):
                tok = re.sub(r"[^\w-]+", "", tok)
                if len(tok) >= 3 and tok not in kws:
                    kws.append(tok)
    except OSError:
        pass

    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for k in kws:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _kebab(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _collect_shared_files(v0_root: Path) -> list[str]:
    """Return shared files list under shared: key."""
    out: list[str] = []
    for rel in SHARED_GLOBS:
        candidate = v0_root / rel
        if rel.endswith(".tsx") or rel.endswith(".css"):
            if candidate.is_file():
                out.append(f"{v0_root.name}/{rel}")
        else:
            # Directory glob — record with ** suffix
            if candidate.is_dir():
                out.append(f"{v0_root.name}/{rel}/**")
    return out


def _extract_manual_lines(manifest_path: Path) -> list[str]:
    """Return lines from an existing manifest that end with '# manual'."""
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [ln for ln in lines if ln.rstrip().endswith(MANUAL_MARKER)]


def _report_scope_keyword_collisions(m: Manifest) -> None:
    """Emit warning on duplicate keywords across routes; raise on identical lists."""
    keyword_to_routes: dict[str, list[str]] = {}
    for r in m.routes:
        for k in r.scope_keywords:
            keyword_to_routes.setdefault(k, []).append(r.path)
    for k, paths in keyword_to_routes.items():
        if len(set(paths)) > 1:
            logger.warning(
                "scope_keyword '%s' maps to multiple routes: %s (consider hand-editing)",
                k, ", ".join(sorted(set(paths))),
            )
    # Identical keyword lists across routes → error
    by_list: dict[tuple, list[str]] = {}
    for r in m.routes:
        key = tuple(sorted(r.scope_keywords))
        by_list.setdefault(key, []).append(r.path)
    for key, paths in by_list.items():
        if len(paths) > 1 and key:
            raise ManifestError(
                f"routes have identical scope_keywords {list(key)}: "
                f"{', '.join(paths)}. Hand-edit to disambiguate."
            )


# ─── Scope matching ────────────────────────────────────────────────


def match_routes_by_scope(
    manifest: Manifest,
    scope: str,
    strict: bool = False,
) -> list[RouteEntry]:
    """Return routes whose scope_keywords substring-match the scope text.

    Matches multiple routes when the scope spans them; empty when no match.

    When ``strict=True`` (for verification gates), prefer verbatim path
    mentions (e.g. ``/admin/termekek``) over keyword substring matches.
    Keyword matching is used only as a fallback when no paths appear in
    the scope text, and even then requires word-boundary matches to
    avoid generic DB field names (``slug``, ``id``) matching routes that
    happen to include dynamic segments.
    """
    import re as _re

    scope_l = (scope or "").lower()
    if not scope_l:
        return []

    if strict:
        # Path-first: if any manifest route path appears literally in scope,
        # use that set and skip keyword fallback entirely.
        path_matches: list[RouteEntry] = []
        for r in manifest.routes:
            rp = r.path.lower()
            if rp == "/":
                continue  # bare "/" is too ambiguous to match verbatim
            # Match as whole path (surrounded by non-word chars or end).
            if _re.search(r"(?<![\w/])" + _re.escape(rp) + r"(?![\w/])", scope_l):
                path_matches.append(r)
        if path_matches:
            return path_matches

        # Fallback: word-boundary keyword match. Rejects generic keywords
        # derived from dynamic segments (``slug``, ``id``) that otherwise
        # cause cross-route false positives.
        _generic = {"slug", "id", "api"}
        matches: list[RouteEntry] = []
        for r in manifest.routes:
            for k in r.scope_keywords:
                if not k or k.lower() in _generic:
                    continue
                if _re.search(r"\b" + _re.escape(k.lower()) + r"\b", scope_l):
                    matches.append(r)
                    break
        return matches

    # Default (legacy, generous): plain substring match on keywords.
    # Used by dispatcher's Focus Files hint — over-inclusion is fine there.
    matches = []
    for r in manifest.routes:
        for k in r.scope_keywords:
            if k and k in scope_l:
                matches.append(r)
                break
    return matches


def match_routes_by_explicit(
    manifest: Manifest,
    design_routes: Iterable[str],
) -> list[RouteEntry]:
    """Return routes whose path is in the explicit design_routes list.

    Raises ManifestError if any listed route is absent from the manifest.
    """
    resolved: list[RouteEntry] = []
    for rp in design_routes:
        entry = manifest.route_by_path(rp)
        if entry is None:
            raise ManifestError(
                f"design_route {rp} not found in manifest. "
                f"Plan stale or manifest changed; regenerate plan."
            )
        resolved.append(entry)
    return resolved


def is_ui_bound_scope(scope: str) -> bool:
    """Heuristic: scope mentions any UI keyword or matches a manifest segment."""
    if not scope:
        return False
    scope_l = scope.lower()
    return any(kw in scope_l for kw in UI_KEYWORDS)
