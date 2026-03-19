"""
set-core - AI-Assisted Development Workflow

A toolkit for AI-assisted development with git worktrees.
"""

__version__ = "1.0.0"

from .plugins import Plugin, PluginRegistry

__all__ = ["Plugin", "PluginRegistry", "__version__"]
