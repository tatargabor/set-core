"""
set-core Plugin System

Provides a plugin architecture for optional integrations.
"""

from .base import Plugin, PluginRegistry

__all__ = ["Plugin", "PluginRegistry"]
