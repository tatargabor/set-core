"""ProjectTypeResolver — merges package rules with local YAML overlay.

Resolution order:
1. Package rules (BaseProjectType → WebProjectType → custom)
2. project-type.yaml overlay (custom_rules, disabled_rules, rule_overrides)
3. .local-overrides.yaml (same format, gitignored, personal)
"""

import warnings
from copy import deepcopy
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

from .profile_types import (
    OrchestrationDirective,
    ProjectType,
    VerificationRule,
)


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file, returning empty dict if missing or yaml unavailable."""
    if yaml is None:
        warnings.warn("PyYAML not installed — YAML overlay not available")
        return {}
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow merge override into base config dict."""
    merged = dict(base)
    merged.update(override)
    return merged


class ProjectTypeResolver:
    """Resolves final rules/directives from package type + local YAML overlay."""

    def __init__(self, project_type: ProjectType, overlay_path: Path):
        self.project_type = project_type
        self.overlay_path = overlay_path
        self._overlay = _load_yaml(overlay_path)

        # Check for .local-overrides.yaml in same directory
        self._local_path = overlay_path.parent / ".local-overrides.yaml"
        self._local = _load_yaml(self._local_path)

        self._warnings: List[str] = []

    def resolve_rules(self) -> List[VerificationRule]:
        """Package rules + custom - disabled, with overrides applied."""
        rules = list(self.project_type.get_verification_rules())
        rules = self._apply_overlay_rules(rules, self._overlay)
        rules = self._apply_overlay_rules(rules, self._local)
        return rules

    def resolve_directives(self) -> List[OrchestrationDirective]:
        """Package directives + custom - disabled."""
        directives = list(self.project_type.get_orchestration_directives())
        directives = self._apply_overlay_directives(directives, self._overlay)
        directives = self._apply_overlay_directives(directives, self._local)
        return directives

    def _apply_overlay_rules(
        self, rules: List[VerificationRule], overlay: Dict[str, Any]
    ) -> List[VerificationRule]:
        if not overlay:
            return rules

        # Disabled rules
        disabled = set(overlay.get("disabled_rules", []))
        existing_ids = {r.id for r in rules}
        for d_id in disabled:
            if d_id not in existing_ids:
                self._warnings.append(f"disabled_rules: unknown rule '{d_id}'")

        rules = [r for r in rules if r.id not in disabled]

        # Rule overrides (merge config)
        overrides = overlay.get("rule_overrides", {})
        if overrides:
            for i, rule in enumerate(rules):
                if rule.id in overrides:
                    ov = overrides[rule.id]
                    updated = deepcopy(rule)
                    if "config" in ov:
                        updated.config = _merge_config(updated.config, ov["config"])
                    if "severity" in ov:
                        updated.severity = ov["severity"]
                    rules[i] = updated

        # Custom rules (append)
        for cr in overlay.get("custom_rules", []):
            rules.append(VerificationRule(
                id=cr["id"],
                description=cr.get("description", ""),
                check=cr.get("check", "custom"),
                severity=cr.get("severity", "warning"),
                config=cr.get("config", {}),
                ignore=cr.get("ignore", []),
            ))

        return rules

    def _apply_overlay_directives(
        self, directives: List[OrchestrationDirective], overlay: Dict[str, Any]
    ) -> List[OrchestrationDirective]:
        if not overlay:
            return directives

        # Disabled directives
        disabled = set(overlay.get("disabled_directives", []))
        existing_ids = {d.id for d in directives}
        for d_id in disabled:
            if d_id not in existing_ids:
                self._warnings.append(f"disabled_directives: unknown directive '{d_id}'")

        directives = [d for d in directives if d.id not in disabled]

        # Custom directives (append)
        for cd in overlay.get("custom_directives", []):
            directives.append(OrchestrationDirective(
                id=cd["id"],
                description=cd.get("description", ""),
                trigger=cd.get("trigger", ""),
                action=cd.get("action", "warn"),
                config=cd.get("config", {}),
            ))

        return directives

    def get_warnings(self) -> List[str]:
        """Return warnings generated during resolution."""
        return list(self._warnings)

    def summary(self) -> Dict[str, Any]:
        """Return counts for rules and directives."""
        pkg_rules = self.project_type.get_verification_rules()
        pkg_directives = self.project_type.get_orchestration_directives()

        resolved_rules = self.resolve_rules()
        resolved_directives = self.resolve_directives()

        all_overlays = [self._overlay, self._local]
        disabled_r = set()
        overridden_r = set()
        custom_r = 0
        disabled_d = set()
        custom_d = 0

        for ov in all_overlays:
            if not ov:
                continue
            disabled_r.update(ov.get("disabled_rules", []))
            overridden_r.update(ov.get("rule_overrides", {}).keys())
            custom_r += len(ov.get("custom_rules", []))
            disabled_d.update(ov.get("disabled_directives", []))
            custom_d += len(ov.get("custom_directives", []))

        return {
            "rules": {
                "total": len(resolved_rules),
                "from_package": len(pkg_rules),
                "custom": custom_r,
                "disabled": len(disabled_r),
                "overridden": len(overridden_r),
            },
            "directives": {
                "total": len(resolved_directives),
                "from_package": len(pkg_directives),
                "custom": custom_d,
                "disabled": len(disabled_d),
            },
        }
