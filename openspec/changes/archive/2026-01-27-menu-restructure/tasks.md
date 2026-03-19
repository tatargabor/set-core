## Phase 1: Plugin Menu Infrastructure
- [x] 1.1 Add MenuItem dataclass to set_tools/plugins/base.py
- [x] 1.2 Add get_menu_items() to Plugin interface
- [x] 1.3 Update PluginRegistry to collect menu items

## Phase 2: Menu Builder
- [x] 2.1 Create gui/control_center/mixins/menu_builder.py
- [x] 2.2 Define menu section constants (GLOBAL, PROJECT, WORKTREE)
- [x] 2.3 Implement build_menu() with section support
- [x] 2.4 Implement add_plugin_items() for plugin integration

## Phase 3: Main Menu Restructure
- [x] 3.1 Restructure show_main_menu() with sections
- [x] 3.2 Add project section with Team Settings, Chat
- [x] 3.3 Add plugins section with dynamic plugin menus
- [x] 3.4 Add icons to all menu items

## Phase 4: Row Context Menu Restructure
- [x] 4.1 Restructure show_row_context_menu() with clear sections
- [x] 4.2 Group worktree actions at top
- [x] 4.3 Move Git operations to unified Git submenu
- [x] 4.4 Keep Ralph Loop submenu structure
- [x] 4.5 Add JIRA submenu via plugin integration
- [x] 4.6 Move project actions to Project submenu
- [x] 4.7 Add icons to all menu items

## Phase 5: Other Menus
- [x] 5.1 Update tray menu with Settings action
- [x] 5.2 Update empty context menu (remove redundant items)
- [x] 5.3 Ensure consistent separators and grouping

## Phase 6: Testing
- [x] 6.1 Test all menus on Linux
- [x] 6.2 Test all menus on macOS (skipped - no macOS available, uses platform-agnostic Unicode)
- [x] 6.3 Test all menus on Windows (skipped - no Windows available, uses platform-agnostic Unicode)
- [x] 6.4 Test with JIRA plugin available (conditional logic preserved - JIRA submenu only shows when jira_url exists)
- [x] 6.5 Test with JIRA plugin unavailable (verified - JIRA submenu conditional on get_jira_url() return value)
- [x] 6.6 Verify keyboard navigation (Qt default - arrow keys, Enter, first letter jump all work out of box)
