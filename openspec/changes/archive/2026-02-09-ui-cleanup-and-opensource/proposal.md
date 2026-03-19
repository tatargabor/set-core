## Why

The Control Center GUI has a "Change" column that's misleading — it actually shows the worktree branch name, not a "change" concept. Additionally, the entire Atlassian integration (JIRA + Confluence) needs to be removed — there will be no Atlassian connection, just a plain GitHub project with a README. Finally, the codebase contains personal/internal references (GitHub usernames, company JIRA URLs) that must be cleaned up before open-sourcing.

## What Changes

- **BREAKING** Rename the "Change" table column to "Branch" in the Control Center GUI and update all related references (change_id → branch name semantics)
- **BREAKING** Remove ALL JIRA integration: `bin/wt-jira` CLI, `bin/jira-move-subtask.py`, `bin/wt-activity`, GUI mixin/dialogs/menus/settings tab/"J" column, `.claude/commands/jira/` commands, JIRA skills, OpenSpec JIRA specs, JIRA config files and templates
- **BREAKING** Remove ALL Confluence integration: `bin/wt-docs-upload`, `bin/docs-upload`, `bin/docs-gen`, `bin/md2confluence`, `docs/confluence.md`, OpenSpec confluence-docs spec, `.set-core/confluence.json(.example)`
- Replace personal GitHub username (`tatargabor`) with the correct public repo URL in README.md, CONTRIBUTING.md, pyproject.toml, docs/config.md
- Clean up archived OpenSpec changes that contain internal company references (`jira.zengo.eu`, `ARVRMTEAM`, personal names)
- Remove OpenSpec CLI from `install.sh` — it's a per-project dev tool, not a set-core runtime dependency
- Change default color profile from "light" to "gray" in `gui/constants.py`
- Fix chat icon click bug: `show_chat_dialog` signature mismatch between table button (passes project arg) and method definition (takes no args)
- Replace git-commit-hash versioning with proper semver from `pyproject.toml` (start at v0.1.0)

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `control-center`: Table column renamed from "Change" to "Branch"; "J" (JIRA) column removed; JIRA submenu removed from context menu; JIRA settings tab removed; default theme changed to gray; version display uses semver from pyproject.toml; chat icon click fixed
- `menu-system`: JIRA submenu entries removed from context menu
- `worktree-tools`: JIRA-related commands (`wt-jira`) and Confluence-related commands (`docs-gen`, `docs-upload`, `wt-docs-upload`, `md2confluence`) removed from the toolset; OpenSpec removed from install.sh

## Impact

- **GUI**: Table header, column rendering, context menus, settings dialog, dialogs module all affected
- **CLI**: `bin/wt-jira`, `bin/jira-move-subtask.py`, `bin/wt-activity`, `bin/wt-docs-upload`, `bin/docs-upload`, `bin/docs-gen`, `bin/md2confluence` deleted
- **Claude commands/skills**: All JIRA-related commands and skills deleted
- **Config**: JIRA defaults removed from `gui/constants.py`, JIRA property removed from `gui/config.py`; Confluence config files deleted
- **OpenSpec specs**: `jira-integration/`, `jira-worklog/`, and `confluence-docs/` spec directories deleted
- **Documentation**: README.md, CONTRIBUTING.md, docs/config.md updated; `docs/confluence.md` deleted
- **Install scripts**: JIRA and Confluence scripts removed from `install.sh` and `install.ps1`; OpenSpec install function removed
- **Version**: `gui/utils.py` `get_version()` reads from `pyproject.toml` instead of git commit hash; `pyproject.toml` version set to `0.1.0`
- **No runtime dependencies change** — JIRA and Confluence were already optional
