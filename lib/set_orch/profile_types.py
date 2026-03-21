"""Project type plugin interface — ABC and dataclasses.

Defines the ProjectType interface that all project knowledge plugins
must implement, plus the data structures they use.

Migrated from: set-project-base/set_project_base/base.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ProjectTypeInfo:
    """Metadata about a project type plugin."""
    name: str
    version: str
    description: str
    parent: Optional[str] = None  # e.g., "web" extends "base"


@dataclass
class TemplateInfo:
    """A template variant provided by a project type."""
    id: str  # e.g., "nextjs", "spa"
    description: str
    template_dir: str  # relative to plugin package


@dataclass
class VerificationRule:
    """A declarative verification rule."""
    id: str
    description: str
    check: str  # check type: cross-file-key-parity, file-mentions, etc.
    severity: str = "warning"  # error, warning, info
    config: Dict[str, Any] = field(default_factory=dict)
    ignore: List[str] = field(default_factory=list)


@dataclass
class OrchestrationDirective:
    """An orchestration guardrail."""
    id: str
    description: str
    trigger: str  # trigger expression
    action: str  # action type: serialize, warn, flag-for-review, post-merge
    config: Dict[str, Any] = field(default_factory=dict)


class ProjectType(ABC):
    """Base class for project type plugins.

    Project types provide domain-specific knowledge to set-core:
    - Templates for project-knowledge.yaml and .claude/rules/
    - Verification rules for opsx:verify
    - Orchestration directives for the sentinel

    Only `info` and `get_templates` are abstract — all other methods
    have default (empty/no-op) implementations so plugins only override
    what they need.
    """

    @property
    @abstractmethod
    def info(self) -> ProjectTypeInfo:
        """Return project type metadata."""

    @abstractmethod
    def get_templates(self) -> List[TemplateInfo]:
        """Return available template variants."""

    def get_template_dir(self, template_id: str) -> Optional[Path]:
        """Return the directory containing template files for a variant."""
        import inspect

        for tmpl in self.get_templates():
            if tmpl.id == template_id:
                cls_file = inspect.getfile(type(self))
                pkg_dir = Path(cls_file).parent
                return pkg_dir / tmpl.template_dir
        return None

    # --- Rules and directives ---

    def get_verification_rules(self) -> List[VerificationRule]:
        return []

    def get_orchestration_directives(self) -> List[OrchestrationDirective]:
        return []

    def get_all_verification_rules(self) -> List[VerificationRule]:
        return self.get_verification_rules()

    def get_all_orchestration_directives(self) -> List[OrchestrationDirective]:
        return self.get_orchestration_directives()

    # --- Profile methods (engine integration) ---

    def planning_rules(self) -> str:
        return ""

    def security_rules_paths(self, project_path: str) -> List[Path]:
        return []

    def security_checklist(self) -> str:
        return ""

    def generated_file_patterns(self) -> list:
        return []

    def lockfile_pm_map(self) -> list:
        return []

    def detect_package_manager(self, project_path: str) -> Optional[str]:
        d = Path(project_path)
        for lockfile, pm in self.lockfile_pm_map():
            if (d / lockfile).is_file():
                return pm
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
        return []

    def register_gates(self) -> list:
        """Return domain-specific GateDefinitions for this project type.

        Override in subclass to register gates like e2e, lint, etc.
        Returns list of GateDefinition instances.
        """
        return []

    def gate_overrides(self, change_type: str) -> dict:
        return {}

    def rule_keyword_mapping(self) -> dict:
        return {}

    def get_forbidden_patterns(self) -> list:
        return []

    def generate_smoke_e2e(self, project_path: str) -> Optional[str]:
        return None

    def pre_dispatch_checks(self, change_type: str, wt_path: str) -> list:
        return []

    def post_verify_hooks(self, change_name: str, wt_path: str, gate_results: list) -> None:
        pass

    def post_merge_hooks(self, change_name: str, state_file: str) -> None:
        """Run profile-specific post-merge operations (i18n sidecar merge, codegen, etc.)."""
        pass

    def decompose_hints(self) -> list:
        return []
