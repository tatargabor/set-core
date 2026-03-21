"""Load project-type profile for orchestration engine integration.

Reads wt/plugins/project-type.yaml to find the active project type,
then loads it via Python entry_points (same mechanism as set-project init).

Provides a singleton cache so profile is loaded once per engine session.
Falls back to NullProfile when no project type is configured or the
plugin package is not installed.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_cached_profile = None
_cache_loaded: bool = False


class NullProfile:
    """Fallback profile when no project type plugin is available.

    All methods return empty/no-op values, so engine falls back
    to its legacy hardcoded behavior.
    """

    def planning_rules(self) -> str:
        return ""

    def security_rules_paths(self, project_path: str) -> list:
        return []

    def security_checklist(self) -> str:
        return ""

    def generated_file_patterns(self) -> list:
        return []

    def lockfile_pm_map(self) -> list:
        return []

    def detect_package_manager(self, project_path: str) -> Optional[str]:
        return None

    def detect_test_command(self, project_path: str) -> Optional[str]:
        return None

    def detect_build_command(self, project_path: str) -> Optional[str]:
        return None

    def detect_e2e_command(self, project_path: str) -> Optional[str]:
        return None

    def detect_dev_server(self, project_path: str) -> Optional[str]:
        return None

    def bootstrap_worktree(self, project_path: str, wt_path: str) -> bool:
        return True

    def post_merge_install(self, project_path: str) -> bool:
        return True

    def ignore_patterns(self) -> list:
        return []

    def merge_strategies(self) -> list:
        """Return list of merge strategy dicts for file-type-aware merge protection.

        Each dict: {name, patterns, strategy, entity_pattern, validate_command, llm_hint}
        Override in project-type plugins to provide defaults (e.g., Prisma for web projects).
        """
        return []

    def gate_overrides(self, change_type: str) -> dict:
        return {}

    def rule_keyword_mapping(self) -> dict:
        """Return mapping of category names to keyword lists and rule glob patterns.

        Used by dispatcher for proactive rule injection at dispatch time.
        Override in project-type plugins to customize per-project.
        """
        return {}

    def get_forbidden_patterns(self) -> list:
        """Return forbidden patterns for the lint gate.

        Each pattern is a dict: {pattern: str (regex), severity: "critical"|"warning",
        message: str, file_glob: str (optional — restrict to matching files)}.
        Override in project-type plugins to provide framework-specific anti-patterns.
        """
        return []

    def get_verification_rules(self) -> list:
        """Return verification rules for the verify gate.

        Override in project-type plugins to provide domain-specific rules.
        """
        return []

    def get_orchestration_directives(self) -> list:
        """Return orchestration directives for engine dispatch/post-merge.

        Override in project-type plugins to provide domain-specific directives.
        """
        return []

    def generate_smoke_e2e(self, project_path: str) -> str | None:
        """Generate route-level smoke E2E test content.

        Returns Playwright test file content as a string, or None if not applicable.
        Override in project-type plugins (e.g., set-project-web) to auto-generate
        tests that visit every route, check for hydration errors, and assert no
        console errors.
        """
        return None

    def pre_dispatch_checks(self, change_type: str, wt_path: str) -> list[str]:
        """Return list of error messages for pre-dispatch validation.

        Empty list means all checks pass. Non-empty blocks dispatch.
        Override in project-type plugins to validate environment before agent starts.
        """
        return []

    def post_verify_hooks(self, change_name: str, wt_path: str, gate_results: list) -> None:
        """Run post-verify side effects (screenshots, cleanup, etc.).

        Called after gate pipeline passes, before merge queue addition.
        Exceptions are caught and logged — do not block merge.
        Override in project-type plugins for domain-specific post-verify actions.
        """
        pass

    def decompose_hints(self) -> list:
        """Return natural-language hints for the decompose/planning prompt.

        Each string is appended to the planning prompt as-is.
        Override in project-type plugins to influence change decomposition.
        """
        return []

    @property
    def info(self):
        from dataclasses import dataclass

        @dataclass
        class _Info:
            name: str = "null"
            version: str = "0.0.0"
            description: str = "No project type configured"

        return _Info()


def load_profile(project_path: str = "."):
    """Load the active project type profile.

    Resolution:
    1. Read wt/plugins/project-type.yaml -> get type name
    2. Load via importlib.metadata entry_points(group='set_tools.project_types')
    3. Instantiate and return
    4. On any failure -> return NullProfile (engine falls back to legacy)

    Default project_path="." works with the engine's CWD convention
    (sentinel always runs from project root). Resolved to absolute path
    for stable cache key.
    """
    global _cached_profile, _cache_loaded

    if _cache_loaded:
        return _cached_profile

    _cache_loaded = True
    project_path = str(Path(project_path).resolve())

    pt_file = Path(project_path) / "wt" / "plugins" / "project-type.yaml"
    if not pt_file.is_file():
        logger.debug("No project-type.yaml found, using NullProfile")
        _cached_profile = NullProfile()
        return _cached_profile

    try:
        import yaml

        with open(pt_file) as f:
            config = yaml.safe_load(f)
        type_name = config.get("type", "")
    except Exception as e:
        logger.warning("Failed to read project-type.yaml: %s", e)
        _cached_profile = NullProfile()
        return _cached_profile

    if not type_name:
        _cached_profile = NullProfile()
        return _cached_profile

    # Load via entry_points (same mechanism as set-project init)
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
                    "Loaded profile: %s v%s",
                    _cached_profile.info.name,
                    _cached_profile.info.version,
                )
                return _cached_profile
            except Exception as e:
                logger.warning("Failed to load profile '%s': %s", type_name, e)
                break

    # Fallback: direct import when entry_points lookup fails
    # (common with editable installs where entry_points aren't registered)
    try:
        import importlib

        mod = importlib.import_module(f"set_project_{type_name}")
        # Look for a class ending with "ProjectType"
        cls = None
        for attr_name in dir(mod):
            if attr_name.endswith("ProjectType") and attr_name != "ProjectType":
                candidate = getattr(mod, attr_name)
                if isinstance(candidate, type):
                    cls = candidate
                    break
        if cls is not None:
            _cached_profile = cls()
            logger.info(
                "Loaded profile via direct import fallback: %s v%s",
                _cached_profile.info.name,
                _cached_profile.info.version,
            )
            return _cached_profile
        logger.warning(
            "Module set_project_%s found but no *ProjectType class", type_name
        )
    except ImportError:
        logger.warning(
            "Profile '%s' not found in entry_points and set_project_%s not importable",
            type_name, type_name,
        )
    except Exception as e:
        logger.warning("Direct import fallback failed for '%s': %s", type_name, e)

    _cached_profile = NullProfile()
    return _cached_profile


def reset_cache():
    """Reset the profile cache (for testing)."""
    global _cached_profile, _cache_loaded
    _cached_profile = None
    _cache_loaded = False
