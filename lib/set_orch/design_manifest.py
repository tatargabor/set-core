"""Layer 1 design manifest dataclasses (design-source-agnostic).

These dataclasses are shared between design source providers (v0, future
claude-design / figma plugins, etc.). The schema mirrors the YAML manifest
that lives at `<project>/docs/design-manifest.yaml`.

Originally lived in `modules/web/set_project_web/v0_manifest.py`; relocated
to Layer 1 by `design-binding-completeness` so non-v0 providers can reuse
the same data model without depending on the web module.

Backward compat: `v0_manifest.py` re-exports `Manifest`, `RouteEntry`,
`ManifestError`, `NoMatchingRouteError` so existing imports keep working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


@dataclass
class RouteEntry:
    """A single route entry from the design manifest.

    Mirrors v0's `app/<path>/page.tsx` plus its component dependencies.
    """

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
class ShellComponent:
    """A shell component (used by ≥2 pages).

    Auto-detected by `set-design-import --regenerate-manifest` via static
    import-graph scan, plus a hardcoded baseline of always-shared paths
    (header, footer, layout, globals.css). Surfaces in
    `Manifest.shared` for fidelity-gate skeleton checks and for the
    shell-shadow detection pass.
    """

    path: str  # absolute or relative to project root, e.g. v0-export/components/site-header.tsx
    importer_count: int = 0  # how many pages import this (≥2 for auto-detect)
    importer_paths: list[str] = field(default_factory=list)
    is_baseline: bool = False  # True if from hardcoded SHARED_GLOBS, not auto-detect

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "importer_count": self.importer_count,
            "importer_paths": list(self.importer_paths),
            "is_baseline": self.is_baseline,
        }


class HygieneSeverity(str, Enum):
    """Severity tier for design-source hygiene findings.

    CRITICAL: blocks design adoption (broken routes, header inconsistency, MOCK arrays).
    WARN: degrades agent quality (i18n leakage, action-handler stubs, type any).
    INFO: potential cleanup (placeholder URLs, inline lambda body, dead routes).
    """

    CRITICAL = "critical"
    WARN = "warn"
    INFO = "info"


@dataclass
class HygieneFinding:
    """A single quality finding emitted by the hygiene scanner.

    Designed to be source-agnostic so v0, claude-design, and figma providers
    can produce comparable findings.
    """

    rule: str  # e.g. "mock-arrays-inline", "broken-route-reference"
    severity: HygieneSeverity
    file: str  # path relative to design source root
    line: int  # 1-based; 0 if not applicable to a single line
    message: str  # human-readable description
    suggested_fix: str = ""  # optional remediation hint
    extra: dict = field(default_factory=dict)  # rule-specific structured data

    def to_dict(self) -> dict:
        d = {
            "rule": self.rule,
            "severity": self.severity.value,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }
        if self.suggested_fix:
            d["suggested_fix"] = self.suggested_fix
        if self.extra:
            d["extra"] = dict(self.extra)
        return d


@dataclass
class Manifest:
    """Project-level design manifest.

    Persisted as YAML at `<project>/docs/design-manifest.yaml`. The shape
    must remain backward-compatible with manifests authored against the
    `v0-only-design-pipeline` foundation.
    """

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
    """Raised when a UI-bound scope has no matching route in the manifest."""
