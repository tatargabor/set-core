"""Manager configuration loading."""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .supervisor import ProjectConfig
from ..issues.policy import IssuesPolicyConfig


@dataclass
class ManagerConfig:
    port: int = 3112
    tick_interval_seconds: int = 5
    set_core_path: Path = field(default_factory=lambda: Path.cwd())
    config_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "share" / "set-core" / "manager")

    projects: dict[str, ProjectConfig] = field(default_factory=dict)
    issues: IssuesPolicyConfig = field(default_factory=IssuesPolicyConfig)

    def to_dict(self) -> dict:
        return {
            "manager": {
                "port": self.port,
                "tick_interval_seconds": self.tick_interval_seconds,
                "set_core_path": str(self.set_core_path),
                "projects": {
                    name: cfg.to_dict() for name, cfg in self.projects.items()
                },
            },
            "issues": {
                "enabled": self.issues.enabled,
                "timeout_by_severity": self.issues.timeout_by_severity,
                "modes": self.issues.modes,
                "auto_fix_conditions": self.issues.auto_fix_conditions,
                "always_manual": self.issues.always_manual,
                "auto_fix_severity": self.issues.auto_fix_severity,
            },
        }

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> ManagerConfig:
        """Load config from YAML file."""
        cfg = cls()

        if config_path is None:
            config_path = cfg.config_dir / "config.yaml"

        if not config_path.exists():
            return cfg

        try:
            data = yaml.safe_load(config_path.read_text()) or {}
        except (yaml.YAMLError, OSError):
            return cfg

        mgr = data.get("manager", {})
        cfg.port = mgr.get("port", 3112)
        cfg.tick_interval_seconds = mgr.get("tick_interval_seconds", 5)
        if "set_core_path" in mgr:
            cfg.set_core_path = Path(mgr["set_core_path"])

        for name, proj_data in mgr.get("projects", {}).items():
            proj_data["name"] = name
            cfg.projects[name] = ProjectConfig.from_dict(proj_data)

        issues_data = data.get("issues", {})
        cfg.issues = IssuesPolicyConfig.from_dict(issues_data)

        return cfg

    def save(self, config_path: Optional[Path] = None):
        """Save config to YAML."""
        if config_path is None:
            config_path = self.config_dir / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.dump(self.to_dict(), default_flow_style=False))

    def add_project(self, name: str, path: Path, mode: str = "e2e") -> ProjectConfig:
        proj = ProjectConfig(name=name, path=path, mode=mode)
        self.projects[name] = proj
        return proj

    def remove_project(self, name: str):
        self.projects.pop(name, None)
