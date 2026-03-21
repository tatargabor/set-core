"""Backwards compatibility shim for set-project-base.

The base module has been absorbed into set-core. This shim re-exports
all public symbols so that `from set_project_base import BaseProjectType`
continues to work for external plugins.
"""

from set_orch.profile_types import (
    OrchestrationDirective,
    ProjectType,
    ProjectTypeInfo,
    TemplateInfo,
    VerificationRule,
)
from set_orch.profile_loader import CoreProfile as BaseProjectType
from set_orch.profile_resolver import ProjectTypeResolver

__all__ = [
    "BaseProjectType",
    "OrchestrationDirective",
    "ProjectType",
    "ProjectTypeInfo",
    "ProjectTypeResolver",
    "TemplateInfo",
    "VerificationRule",
]
