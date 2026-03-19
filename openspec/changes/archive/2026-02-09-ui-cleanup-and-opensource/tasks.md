## 1. Rename "Change" column to "Branch"

- [x] 1.1 Rename table header from "Name" to "Branch" in `gui/control_center/main_window.py`
- [x] 1.2 Column count stays at 6 (Extra column kept for Ralph indicator)
- [x] 1.3 Update column references in `gui/control_center/mixins/table.py` (JIRA comment cleaned)
- [x] 1.4 No "change" references in context menu display text needed updating

## 2. Remove JIRA from GUI

- [x] 2.1 Remove `JiraMixin` import and inheritance from `gui/control_center/main_window.py`
- [x] 2.2 Delete `gui/control_center/mixins/jira.py`
- [x] 2.3 Delete `gui/dialogs/jira_sync.py` and remove from `gui/dialogs/__init__.py`
- [x] 2.4 Remove JIRA tab from `gui/dialogs/settings.py`
- [x] 2.5 Remove JIRA references from `gui/dialogs/worktree_config.py`
- [x] 2.6 Remove JIRA button from Extra column in `gui/control_center/mixins/table.py`
- [x] 2.7 Remove JIRA submenu from context menu in `gui/control_center/mixins/menus.py`
- [x] 2.8 Remove JIRA config defaults from `gui/constants.py`
- [x] 2.9 Remove JIRA config property from `gui/config.py`

## 3. Remove JIRA CLI and commands

- [x] 3.1 Delete `bin/wt-jira`
- [x] 3.2 Delete `bin/jira-move-subtask.py`
- [x] 3.3 Delete `bin/wt-activity` (JIRA worklog file activity tracker)
- [x] 3.4 Delete `.claude/commands/jira/` directory (all 6 command files)
- [x] 3.5 Remove JIRA/Confluence sections from `.claude/skills/wt/SKILL.md`
- [x] 3.6 Delete `.set-core/jira.json` and `.set-core/jira.json.example`
- [x] 3.7 No `.mcp.template.json` exists — skipped

## 4. Remove Confluence CLI and files

- [x] 4.1 Delete `bin/wt-docs-upload`
- [x] 4.2 Delete `bin/docs-upload`
- [x] 4.3 Delete `bin/docs-gen`
- [x] 4.4 Delete `bin/md2confluence`
- [x] 4.5 Delete `docs/confluence.md`
- [x] 4.6 Delete `.set-core/confluence.json` and `.set-core/confluence.json.example`

## 5. Remove Atlassian OpenSpec specs

- [x] 5.1 Delete `openspec/specs/jira-integration/` directory
- [x] 5.2 Delete `openspec/specs/jira-worklog/` directory
- [x] 5.3 Delete `openspec/specs/confluence-docs/` directory
- [x] 5.4 Clean JIRA/Confluence references from `openspec/project.md` and all active specs

## 6. Remove from install scripts

- [x] 6.1 Remove `wt-jira`, `wt-docs-upload`, `docs-gen`, `wt-activity` from `install.sh` scripts list
- [x] 6.2 Remove JIRA commands symlink section from `install.sh`
- [x] 6.3 Remove JIRA/Confluence references from `install.ps1`
- [x] 6.4 Remove JIRA info from install.sh and install.ps1 help/usage output

## 7. Open source cleanup

- [x] 7.1 Replace `tatargabor/set-core` with `anthropic-tools/set-core` in `README.md`, `CONTRIBUTING.md`, `pyproject.toml`, `docs/config.md`
- [x] 7.2 Remove JIRA and Confluence sections from `README.md` and `docs/config.md`
- [x] 7.3 Clean internal references from archived changes (`jira.zengo.eu`, `ARVRMTEAM`, `zengo-mirror`, personal names)

## 8. Remove OpenSpec from install.sh

- [x] 8.1 Delete the `install_openspec()` function from `install.sh` (lines ~237-268)
- [x] 8.2 Remove the `install_openspec` call from the main install flow (line ~806)
- [x] 8.3 Remove any OpenSpec references from `install.ps1` if present

## 9. Default theme to gray

- [x] 9.1 Change `"color_profile": "light"` to `"color_profile": "gray"` in `gui/constants.py` DEFAULT_CONFIG

## 10. Fix chat icon click

- [x] 10.1 Add `project=None` parameter to `show_chat_dialog()` in `gui/control_center/mixins/menus.py`
- [x] 10.2 Use the passed project when available, fall back to `get_active_project()` when None
- [x] 10.3 Remove DEBUG print statements from `show_chat_dialog` and `ChatDialog` methods

## 11. Semver versioning from pyproject.toml

- [x] 11.1 Change `version = "1.0.0"` to `version = "0.1.0"` in `pyproject.toml`
- [x] 11.2 Rewrite `get_version()` in `gui/utils.py` to read version from `pyproject.toml` instead of git commit hash
- [x] 11.3 Verify title bar shows `Worktree Control Center [0.1.0]` and bottom label shows `v0.1.0`
- [x] 11.4 Update test expectations in `tests/gui/test_02_window.py` — no change needed (test only checks title text)

## 12. Testing

- [x] 12.1 Update GUI tests to reflect column rename (test_01_startup.py header expectations)
- [x] 12.2 Run GUI tests: `PYTHONPATH=. python -m pytest tests/gui/ -v --tb=short` — 102/102 passed
