"""V0DesignSourceProvider — consolidates v0-specific design source operations.

Implements the conceptual `DesignSourceProvider` protocol exposed via
`ProjectType` ABC methods (`detect_design_source`, `extract_design_manifest`,
`scan_design_hygiene`, `get_shell_components`). The class is a thin facade
over the existing v0_manifest.py + v0_hygiene_scanner.py + v0_fidelity_gate.py
implementations.

Future design source providers (Claude Design, Figma, etc.) implement the
same interface so downstream consumers (decompose, planner, fidelity gate)
do not need to know which design tool produced the artifacts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from set_orch.design_manifest import HygieneFinding, Manifest


class V0DesignSourceProvider:
    """Facade over v0-specific design-source operations.

    Construction is cheap; the provider holds no state. Methods accept
    `project_path` so the same instance can serve multiple consumer
    projects within one orchestration run.
    """

    SOURCE_ID = "v0"
    EXPORT_DIRNAME = "v0-export"

    def detect(self, project_path: Path) -> str:
        """Return "v0" if `<project_path>/v0-export/` exists, else "none"."""
        if (Path(project_path) / self.EXPORT_DIRNAME).is_dir():
            return self.SOURCE_ID
        return "none"

    def extract_manifest(self, project_path: Path) -> "Manifest":
        """Generate a fresh manifest from the v0-export tree.

        Equivalent to `set-design-import --regenerate-manifest`.
        """
        from .v0_manifest import generate_manifest_from_tree

        v0_dir = Path(project_path) / self.EXPORT_DIRNAME
        manifest_path = Path(project_path) / "docs" / "design-manifest.yaml"
        return generate_manifest_from_tree(v0_dir, manifest_path)

    def load_manifest(self, project_path: Path) -> "Manifest":
        """Load existing manifest from disk; raises if absent."""
        from .v0_manifest import load_manifest

        manifest_path = Path(project_path) / "docs" / "design-manifest.yaml"
        return load_manifest(manifest_path)

    def scan_hygiene(self, project_path: Path) -> list:
        """Run the hygiene scanner against `v0-export/`.

        Returns list of `HygieneFinding` dataclasses. Empty list if
        `v0-export/` is absent (no design source).
        """
        v0_dir = Path(project_path) / self.EXPORT_DIRNAME
        if not v0_dir.is_dir():
            return []
        try:
            from .v0_hygiene_scanner import scan_v0_export
        except ImportError:
            logger.debug(
                "v0_hygiene_scanner not yet implemented (early-phase build); "
                "scan_hygiene returns empty list"
            )
            return []
        # Load manifest if present — needed for route reference integrity rule.
        manifest = None
        manifest_path = Path(project_path) / "docs" / "design-manifest.yaml"
        if manifest_path.is_file():
            try:
                manifest = self.load_manifest(project_path)
            except Exception:
                logger.warning("manifest unparseable; route-integrity rule will be skipped",
                               exc_info=True)
        return scan_v0_export(v0_dir, manifest=manifest)

    def get_shell_components(self, project_path: Path) -> list[str]:
        """Return the manifest's shared-shell list (paths relative to
        project root, e.g. `v0-export/components/site-header.tsx`).

        Reads the persisted manifest. Returns empty list if no manifest.
        """
        manifest_path = Path(project_path) / "docs" / "design-manifest.yaml"
        if not manifest_path.is_file():
            return []
        try:
            from .v0_manifest import load_manifest

            m = load_manifest(manifest_path)
            return list(m.shared)
        except Exception:
            logger.warning(
                "get_shell_components failed for %s (non-blocking)",
                project_path, exc_info=True,
            )
            return []
