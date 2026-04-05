from __future__ import annotations

"""Load project-type profile for orchestration engine integration.

Reads set/plugins/project-type.yaml to find the active project type,
then loads it via:
  1. entry_points (external plugins — highest priority)
  2. direct import (editable install resilience)
  3. built-in modules/ directory (monorepo fallback)
  4. NullProfile (no-op fallback)

Provides CoreProfile with universal rules (file-size, no-secrets, etc.)
that all project types inherit from.
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional

from .profile_types import (
    OrchestrationDirective,
    ProjectType,
    ProjectTypeInfo,
    TemplateInfo,
    VerificationRule,
)

logger = logging.getLogger(__name__)

_cached_profile = None
_cache_loaded: bool = False

# set-core root (lib/set_orch/profile_loader.py → ../../)
_SET_CORE_ROOT = Path(__file__).resolve().parents[2]


class NullProfile(ProjectType):
    """Fallback profile when no project type plugin is available.

    All methods return empty/no-op values. Inherits from ProjectType ABC.
    """

    @property
    def info(self) -> ProjectTypeInfo:
        return ProjectTypeInfo(
            name="null",
            version="0.0.0",
            description="No project type configured",
        )

    def get_templates(self) -> List[TemplateInfo]:
        return []


class CoreProfile(ProjectType):
    """Universal project knowledge built into set-core.

    Provides rules and directives that apply to any software project
    regardless of tech stack. All real project-type plugins should
    inherit from CoreProfile instead of ProjectType directly.

    Replaces: set-project-base BaseProjectType
    """

    @property
    def info(self) -> ProjectTypeInfo:
        return ProjectTypeInfo(
            name="core",
            version="0.3.0",
            description="Universal project knowledge — rules and directives for any project",
        )

    def get_templates(self) -> List[TemplateInfo]:
        return [
            TemplateInfo(
                id="default",
                description="Minimal project knowledge scaffold",
                template_dir="templates/default",
            ),
        ]

    def spec_sections(self) -> List["SpecSection"]:
        from .profile_types import SpecSection
        return [
            SpecSection(
                id="overview",
                title="Project Overview",
                description="Project name, purpose, tech stack, target audience",
                required=True,
                phase=1,
                output_path="docs/spec.md",
                prompt_hint="Tell me about this project in 2-3 sentences. What does it do and who is it for?",
            ),
            SpecSection(
                id="requirements",
                title="Requirements",
                description="Main features/capabilities with REQ-IDs and WHEN/THEN scenarios",
                required=True,
                phase=5,
                output_path="docs/features/{name}.md",
                prompt_hint="What are the main features/capabilities of this project?",
            ),
            SpecSection(
                id="orchestrator_directives",
                title="Orchestrator Directives",
                description="Parallel execution hints, review gates, time limits",
                required=False,
                phase=10,
                output_path="docs/spec.md",
                prompt_hint="How many changes should run in parallel? Should code be reviewed before merge?",
            ),
            SpecSection(
                id="verification_checklist",
                title="Verification Checklist",
                description="Post-run verification items derived from requirements",
                required=False,
                phase=11,
                output_path="docs/spec.md",
                prompt_hint="",  # Auto-generated from requirements
            ),
        ]

    def get_verification_rules(self) -> List[VerificationRule]:
        return [
            VerificationRule(
                id="file-size-limit",
                description="Source files should not exceed 400 lines",
                check="file-line-count",
                severity="warning",
                config={
                    "pattern": "src/**/*.{py,ts,tsx,js,jsx,rs,go}",
                    "max_lines": 400,
                },
            ),
            VerificationRule(
                id="no-secrets-in-source",
                description="Source files should not contain hardcoded secrets",
                check="pattern-absence",
                severity="error",
                config={
                    "pattern": "**/*.{py,ts,tsx,js,jsx,yaml,yml,json}",
                    "forbidden": [
                        r"(?i)(api[_-]?key|secret[_-]?key|password)\s*[:=]\s*['\"][^'\"]{8,}",
                    ],
                    "exclude": ["*.example", "*.test.*", "*.spec.*"],
                },
            ),
            VerificationRule(
                id="todo-tracking",
                description="TODO/FIXME/HACK comments should reference an issue or change",
                check="pattern-audit",
                severity="info",
                config={
                    "pattern": "**/*.{py,ts,tsx,js,jsx}",
                    "match": r"(?i)\b(TODO|FIXME|HACK|XXX)\b",
                },
            ),
        ]

    def get_orchestration_directives(self) -> List[OrchestrationDirective]:
        return [
            OrchestrationDirective(
                id="install-deps-npm",
                description="Install npm dependencies after package.json changes",
                trigger='change-modifies("package.json")',
                action="post-merge",
                config={"command": "npm install"},
            ),
            OrchestrationDirective(
                id="install-deps-python",
                description="Install Python dependencies after pyproject.toml changes",
                trigger='change-modifies("pyproject.toml")',
                action="post-merge",
                config={"command": "pip install -e ."},
            ),
            OrchestrationDirective(
                id="no-parallel-lockfile",
                description="Serialize changes that modify lock files to prevent merge conflicts",
                trigger='change-modifies-any("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock")',
                action="serialize",
                config={"with": 'changes-modifying-any("*lock*")'},
            ),
            OrchestrationDirective(
                id="config-review",
                description="Flag changes to CI/CD and infrastructure config for review",
                trigger='change-modifies-any(".github/**", "Dockerfile", "docker-compose*.yml", ".gitlab-ci.yml")',
                action="flag-for-review",
            ),
        ]


def _find_project_type_class(mod) -> Optional[type]:
    """Find a *ProjectType class in a module (excluding ProjectType itself)."""
    for attr_name in dir(mod):
        if attr_name.endswith("ProjectType") and attr_name != "ProjectType":
            candidate = getattr(mod, attr_name)
            if isinstance(candidate, type):
                return candidate
    return None


def load_profile(project_path: str = "."):
    """Load the active project type profile.

    Resolution order:
    1. Read set/plugins/project-type.yaml → get type name
    2. entry_points(group='set_tools.project_types') — external plugins
    3. direct import set_project_{type_name} — editable install resilience
    4. built-in modules/{type_name}/ — monorepo fallback
    5. NullProfile
    """
    global _cached_profile, _cache_loaded

    if _cache_loaded:
        return _cached_profile

    _cache_loaded = True
    project_path = str(Path(project_path).resolve())

    pt_file = Path(project_path) / "set" / "plugins" / "project-type.yaml"
    if not pt_file.is_file():
        # Task 4.2: no project-type.yaml — expected for non-set-core projects
        logger.debug("No project-type.yaml — using NullProfile")
        _cached_profile = NullProfile()
        return _cached_profile

    try:
        import yaml

        with open(pt_file) as f:
            config = yaml.safe_load(f) or {}
        type_name = config.get("type", "")
    except Exception as e:
        logger.warning("Failed to read project-type.yaml: %s", e)
        _cached_profile = NullProfile()
        return _cached_profile

    if not type_name:
        # Task 4.1: project-type.yaml exists but type is empty/invalid
        logger.warning(
            "[ANOMALY] project-type.yaml found but type '%s' unknown "
            "— using NullProfile (no project-specific knowledge)",
            type_name,
        )
        _cached_profile = NullProfile()
        return _cached_profile

    # Step 1: entry_points (external plugins take priority)
    try:
        from importlib.metadata import entry_points

        eps = entry_points(group="set_tools.project_types")
    except TypeError:
        from importlib.metadata import entry_points

        eps = entry_points().get("set_tools.project_types", [])

    for ep in eps:
        if ep.name == type_name:
            try:
                cls = ep.load()
                _cached_profile = cls()
                logger.info(
                    "Loaded profile via entry_points: %s v%s",
                    _cached_profile.info.name,
                    _cached_profile.info.version,
                )
                return _cached_profile
            except Exception as e:
                logger.warning("Failed to load profile '%s' via entry_points: %s", type_name, e)
                break

    # Step 2: direct import (editable install resilience)
    try:
        import importlib

        mod = importlib.import_module(f"set_project_{type_name}")
        cls = _find_project_type_class(mod)
        if cls is not None:
            _cached_profile = cls()
            logger.info(
                "Loaded profile via direct import: %s v%s",
                _cached_profile.info.name,
                _cached_profile.info.version,
            )
            return _cached_profile
        logger.debug("Module set_project_%s found but no *ProjectType class", type_name)
    except ImportError:
        logger.debug("set_project_%s not directly importable", type_name)
    except Exception as e:
        logger.warning("Direct import failed for '%s': %s", type_name, e)

    # Step 3: built-in modules/ (monorepo fallback)
    modules_dir = _SET_CORE_ROOT / "modules" / type_name
    module_pkg = modules_dir / f"set_project_{type_name}"
    if module_pkg.is_dir() and (module_pkg / "__init__.py").is_file():
        try:
            import importlib

            # Temporarily add module parent to sys.path
            modules_str = str(modules_dir)
            if modules_str not in sys.path:
                sys.path.insert(0, modules_str)
            mod = importlib.import_module(f"set_project_{type_name}")
            cls = _find_project_type_class(mod)
            if cls is not None:
                _cached_profile = cls()
                logger.info(
                    "Loaded profile via built-in module: %s v%s",
                    _cached_profile.info.name,
                    _cached_profile.info.version,
                )
                return _cached_profile
        except Exception as e:
            logger.warning("Built-in module load failed for '%s': %s", type_name, e)

    logger.warning(
        "[ANOMALY] project-type.yaml found but type '%s' unknown "
        "— using NullProfile (no project-specific knowledge)",
        type_name,
    )
    _cached_profile = NullProfile()
    return _cached_profile


def reset_cache():
    """Reset the profile cache (for testing)."""
    global _cached_profile, _cache_loaded
    _cached_profile = None
    _cache_loaded = False
