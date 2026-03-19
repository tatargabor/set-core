"""Tests for the plugin system"""

import pytest
from set_tools.plugins import Plugin, PluginRegistry
from set_tools.plugins.base import PluginInfo, MenuItem, ColumnInfo


class DummyPlugin(Plugin):
    """A test plugin for testing the plugin system"""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin for unit tests",
        )

    def get_menu_items(self, worktree_path: str, project: str):
        return [
            MenuItem(label="Test Action", callback=lambda: None),
        ]

    def get_table_columns(self):
        return [
            ColumnInfo(id="test", label="Test", width=50),
        ]


class TestPluginInfo:
    """Tests for PluginInfo dataclass"""

    def test_create_plugin_info(self):
        info = PluginInfo(
            name="my-plugin",
            version="2.0.0",
            description="A test plugin",
            author="Test Author",
            homepage="https://example.com",
        )
        assert info.name == "my-plugin"
        assert info.version == "2.0.0"
        assert info.description == "A test plugin"
        assert info.author == "Test Author"
        assert info.homepage == "https://example.com"

    def test_plugin_info_defaults(self):
        info = PluginInfo(
            name="minimal",
            version="1.0.0",
            description="Minimal plugin",
        )
        assert info.author == ""
        assert info.homepage == ""


class TestMenuItem:
    """Tests for MenuItem dataclass"""

    def test_create_menu_item(self):
        callback = lambda: print("clicked")
        item = MenuItem(
            label="My Action",
            callback=callback,
            icon="icon.png",
            shortcut="Ctrl+M",
        )
        assert item.label == "My Action"
        assert item.callback == callback
        assert item.icon == "icon.png"
        assert item.shortcut == "Ctrl+M"


class TestColumnInfo:
    """Tests for ColumnInfo dataclass"""

    def test_create_column_info(self):
        col = ColumnInfo(
            id="status",
            label="Status",
            width=100,
            tooltip="Current status",
        )
        assert col.id == "status"
        assert col.label == "Status"
        assert col.width == 100
        assert col.tooltip == "Current status"

    def test_column_info_defaults(self):
        col = ColumnInfo(id="test", label="Test")
        assert col.width == 50
        assert col.tooltip == ""


class TestPluginRegistry:
    """Tests for PluginRegistry"""

    def test_create_registry(self):
        registry = PluginRegistry()
        assert len(registry.get_all_plugins()) == 0

    def test_set_app_context(self):
        registry = PluginRegistry()
        context = {"key": "value"}
        registry.set_app_context(context)
        # Context is stored internally
        assert registry._app_context == context

    def test_discover_plugins(self):
        registry = PluginRegistry()
        # Should not raise even with no plugins
        discovered = registry.discover_plugins()
        assert isinstance(discovered, list)

    def test_is_loaded(self):
        registry = PluginRegistry()
        assert not registry.is_loaded("nonexistent")


class TestDummyPlugin:
    """Tests for the DummyPlugin implementation"""

    def test_plugin_info(self):
        plugin = DummyPlugin()
        info = plugin.info
        assert info.name == "test-plugin"
        assert info.version == "1.0.0"

    def test_initialize(self):
        plugin = DummyPlugin()
        result = plugin.initialize({})
        assert result is True

    def test_shutdown(self):
        plugin = DummyPlugin()
        # Should not raise
        plugin.shutdown()

    def test_get_menu_items(self):
        plugin = DummyPlugin()
        items = plugin.get_menu_items("/path/to/worktree", "project")
        assert len(items) == 1
        assert items[0].label == "Test Action"

    def test_get_table_columns(self):
        plugin = DummyPlugin()
        columns = plugin.get_table_columns()
        assert len(columns) == 1
        assert columns[0].id == "test"

    def test_get_cell_data_default(self):
        plugin = DummyPlugin()
        data = plugin.get_cell_data("test", "/path")
        assert data is None

    def test_get_settings_widget_default(self):
        plugin = DummyPlugin()
        widget = plugin.get_settings_widget(None)
        assert widget is None

    def test_get_cli_commands_default(self):
        plugin = DummyPlugin()
        commands = plugin.get_cli_commands()
        assert commands == {}
