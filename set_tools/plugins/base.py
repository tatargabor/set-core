"""
Plugin Base Class and Registry

Provides the foundation for set-core plugins.
"""

import importlib.metadata
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Type

logger = logging.getLogger(__name__)

__all__ = ["Plugin", "PluginRegistry", "PluginInfo", "MenuItem"]


@dataclass
class PluginInfo:
    """Information about a plugin"""
    name: str
    version: str
    description: str
    author: str = ""
    homepage: str = ""


@dataclass
class MenuItem:
    """A menu item provided by a plugin or internal feature.

    Attributes:
        label: Display text for the menu item
        callback: Function to call when item is clicked
        icon: Unicode emoji or icon identifier (e.g., "⚙️", "↻")
        shortcut: Keyboard shortcut (e.g., "Ctrl+R")
        level: Where this item appears - "global", "project", or "worktree"
        submenu: Optional submenu name (e.g., "Git", "Ralph") - groups items together
        order: Sort order within submenu (lower = higher in menu)
    """
    label: str
    callback: Callable
    icon: Optional[str] = None
    shortcut: Optional[str] = None
    level: Literal["global", "project", "worktree"] = "worktree"
    submenu: Optional[str] = None
    order: int = 100


@dataclass
class ColumnInfo:
    """A table column provided by a plugin"""
    id: str
    label: str
    width: int = 50
    tooltip: str = ""


class Plugin(ABC):
    """
    Base class for set-core plugins.

    Plugins can provide:
    - Menu items for the worktree context menu
    - Columns for the worktree table
    - Settings tabs in the settings dialog
    - CLI commands
    """

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Return plugin information"""
        pass

    def initialize(self, app_context: Dict[str, Any]) -> bool:
        """
        Initialize the plugin.

        Args:
            app_context: Application context with shared resources

        Returns:
            True if initialization was successful
        """
        return True

    def shutdown(self) -> None:
        """Clean up plugin resources"""
        pass

    def get_menu_items(self, worktree_path: str, project: str) -> List[MenuItem]:
        """
        Get menu items provided by this plugin.

        Items can specify their level (global/project/worktree) and optional
        submenu grouping. The menu builder will place items appropriately.

        Args:
            worktree_path: Path to the worktree (may be empty for global items)
            project: Project name (may be empty for global items)

        Returns:
            List of MenuItem objects with level, submenu, and order set
        """
        return []

    def get_table_columns(self) -> List[ColumnInfo]:
        """
        Get additional columns for the worktree table.

        Returns:
            List of column definitions
        """
        return []

    def get_cell_data(self, column_id: str, worktree_path: str) -> Optional[Any]:
        """
        Get data for a cell in a plugin-provided column.

        Args:
            column_id: The column ID
            worktree_path: Path to the worktree

        Returns:
            Cell data (string, widget, etc.) or None
        """
        return None

    def get_settings_widget(self, parent) -> Optional[Any]:
        """
        Get a settings widget for the plugin.

        Args:
            parent: Parent widget

        Returns:
            Settings widget or None if plugin has no settings
        """
        return None

    def get_cli_commands(self) -> Dict[str, Callable]:
        """
        Get CLI commands provided by the plugin.

        Returns:
            Dict mapping command names to handler functions
        """
        return {}


class PluginRegistry:
    """
    Registry for managing plugins.

    Discovers and loads plugins via entry points.
    """

    ENTRY_POINT_GROUP = "set_tools.plugins"

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._app_context: Dict[str, Any] = {}

    def set_app_context(self, context: Dict[str, Any]) -> None:
        """Set the application context for plugins"""
        self._app_context = context

    def discover_plugins(self) -> List[str]:
        """
        Discover available plugins via entry points.

        Returns:
            List of discovered plugin names
        """
        discovered = []

        try:
            # Python 3.10+ style
            entry_points = importlib.metadata.entry_points(group=self.ENTRY_POINT_GROUP)
        except TypeError:
            # Python 3.9 style
            eps = importlib.metadata.entry_points()
            entry_points = eps.get(self.ENTRY_POINT_GROUP, [])

        for ep in entry_points:
            discovered.append(ep.name)

        return discovered

    def load_plugin(self, name: str) -> bool:
        """
        Load and initialize a plugin by name.

        Args:
            name: Plugin name (entry point name)

        Returns:
            True if plugin was loaded successfully
        """
        if name in self._plugins:
            logger.debug(f"Plugin '{name}' already loaded")
            return True

        try:
            # Get entry point
            try:
                entry_points = importlib.metadata.entry_points(group=self.ENTRY_POINT_GROUP)
            except TypeError:
                eps = importlib.metadata.entry_points()
                entry_points = eps.get(self.ENTRY_POINT_GROUP, [])

            ep = None
            for entry_point in entry_points:
                if entry_point.name == name:
                    ep = entry_point
                    break

            if ep is None:
                logger.warning(f"Plugin '{name}' not found")
                return False

            # Load the plugin class
            plugin_class = ep.load()
            if not issubclass(plugin_class, Plugin):
                logger.error(f"Plugin '{name}' does not inherit from Plugin")
                return False

            # Instantiate and initialize
            plugin = plugin_class()
            if not plugin.initialize(self._app_context):
                logger.error(f"Plugin '{name}' failed to initialize")
                return False

            self._plugins[name] = plugin
            logger.info(f"Loaded plugin '{name}' v{plugin.info.version}")
            return True

        except Exception as e:
            logger.error(f"Failed to load plugin '{name}': {e}")
            return False

    def load_all_plugins(self) -> int:
        """
        Discover and load all available plugins.

        Returns:
            Number of successfully loaded plugins
        """
        count = 0
        for name in self.discover_plugins():
            if self.load_plugin(name):
                count += 1
        return count

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a loaded plugin by name"""
        return self._plugins.get(name)

    def get_all_plugins(self) -> Dict[str, Plugin]:
        """Get all loaded plugins"""
        return dict(self._plugins)

    def is_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded"""
        return name in self._plugins

    def unload_plugin(self, name: str) -> bool:
        """
        Unload a plugin.

        Args:
            name: Plugin name

        Returns:
            True if plugin was unloaded
        """
        if name not in self._plugins:
            return False

        try:
            self._plugins[name].shutdown()
            del self._plugins[name]
            logger.info(f"Unloaded plugin '{name}'")
            return True
        except Exception as e:
            logger.error(f"Error unloading plugin '{name}': {e}")
            return False

    def shutdown_all(self) -> None:
        """Shutdown all plugins"""
        for name in list(self._plugins.keys()):
            self.unload_plugin(name)

    # Aggregation methods for GUI

    def get_all_menu_items(
        self,
        worktree_path: str = "",
        project: str = "",
        level: Optional[Literal["global", "project", "worktree"]] = None
    ) -> List[MenuItem]:
        """Get menu items from all plugins.

        Args:
            worktree_path: Path to the worktree (optional for global items)
            project: Project name (optional for global items)
            level: Filter by level (global/project/worktree), or None for all

        Returns:
            List of MenuItem objects, sorted by (submenu, order, label)
        """
        items = []
        for plugin in self._plugins.values():
            plugin_items = plugin.get_menu_items(worktree_path, project)
            if level is not None:
                plugin_items = [i for i in plugin_items if i.level == level]
            items.extend(plugin_items)

        # Sort by submenu (None first), then order, then label
        items.sort(key=lambda i: (i.submenu or "", i.order, i.label))
        return items

    def get_menu_items_by_submenu(
        self,
        worktree_path: str = "",
        project: str = "",
        level: Optional[Literal["global", "project", "worktree"]] = None
    ) -> Dict[Optional[str], List[MenuItem]]:
        """Get menu items grouped by submenu.

        Args:
            worktree_path: Path to the worktree
            project: Project name
            level: Filter by level, or None for all

        Returns:
            Dict mapping submenu name (or None) to list of MenuItems
        """
        items = self.get_all_menu_items(worktree_path, project, level)
        grouped: Dict[Optional[str], List[MenuItem]] = {}
        for item in items:
            if item.submenu not in grouped:
                grouped[item.submenu] = []
            grouped[item.submenu].append(item)
        return grouped

    def get_all_table_columns(self) -> List[ColumnInfo]:
        """Get table columns from all plugins"""
        columns = []
        for plugin in self._plugins.values():
            columns.extend(plugin.get_table_columns())
        return columns

    def get_cell_data(self, column_id: str, worktree_path: str) -> Optional[Any]:
        """Get cell data for a plugin column"""
        for plugin in self._plugins.values():
            data = plugin.get_cell_data(column_id, worktree_path)
            if data is not None:
                return data
        return None


# Global registry instance
_registry: Optional[PluginRegistry] = None


def get_registry() -> PluginRegistry:
    """Get the global plugin registry"""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry
