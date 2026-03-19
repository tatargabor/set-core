## Context

The set-core project is preparing for open source release. Three cleanup areas have been identified:
1. The GUI table "Change" column is misleading — it shows the branch/worktree identifier, not a "change" concept
2. All Atlassian integration (JIRA + Confluence) must be removed — the project will be a plain GitHub project with no Atlassian connection
3. Personal/internal references must be cleaned from documentation and config before publishing

## Goals / Non-Goals

**Goals:**
- Rename "Change" column to "Branch" throughout the GUI
- Remove all JIRA integration code, commands, skills, specs, and config
- Remove all Confluence integration code, commands, specs, and config
- Clean up personal GitHub URLs and internal company references
- Maintain all non-Atlassian GUI functionality unchanged

**Non-Goals:**
- Replacing JIRA/Confluence with another integration — nothing replaces them
- Restructuring the settings dialog beyond removing the JIRA tab
- Changing the `change_id` field name in wt-status JSON output (that's a separate concern)
- Rewriting archived change history (just remove sensitive references)

## Decisions

### 1. Column rename: "Change" → "Branch"
The column displays the extracted branch identifier (from `change/{id}` pattern or worktree basename). "Branch" is the most accurate label. The underlying data field (`change_id`) in wt-status output stays the same for now — only the GUI display label changes.

### 2. Atlassian removal strategy: Delete entirely, don't stub
Rather than leaving empty plugin hooks or stub interfaces, we delete all JIRA and Confluence code completely. The "J" column in the table is removed. The JIRA settings tab is removed. The JIRA context menu submenu is removed. All Confluence CLI tools (`docs-gen`, `docs-upload`, `wt-docs-upload`, `md2confluence`) are deleted. This is cleaner than leaving dead code.

### 3. Table column reduction: 6 → 5 columns
Current columns: `[Project, Change, Status, Skill, Ctx%, J]`
New columns: `[Project, Branch, Status, Skill, Ctx%]`
The "J" column was JIRA-only, so it goes away entirely.

### 4. GitHub URLs: Use placeholder until repo is created
Replace `tatargabor/set-core` with a TBD org/repo pattern. The user will finalize the actual URL.

### 5. Archived changes: Remove internal references
Clean archived change files that contain `jira.zengo.eu`, `ARVRMTEAM`, personal names. These are historical but shouldn't be in a public repo.

### 6. Confluence docs tooling removed entirely
The `docs-gen` command generated Confluence-compatible markdown from OpenSpec specs. Since there's no Confluence, the entire docs generation pipeline is deleted. If documentation generation is needed later, it will be built differently (e.g., GitHub Pages, plain README sections).

### 7. Remove OpenSpec from install.sh
OpenSpec CLI is a per-project developer tool, not a set-core runtime dependency. `openspec init` is run once per project and the resulting `.openspec/` directory lives in git — worktrees get it automatically. Remove the `install_openspec()` function and its call from the main install flow.

### 8. Default theme: gray
The "gray" color profile is the best default for developer use — neither too bright (light) nor too dark (dark). Change `DEFAULT_CONFIG["control_center"]["color_profile"]` from `"light"` to `"gray"`.

### 9. Chat icon click fix
There's a signature mismatch: `table.py:189` connects the chat button with `lambda checked, p=project: self.show_chat_dialog(p)` but `menus.py:345` defines `show_chat_dialog(self)` with no project parameter. Fix: add `project=None` parameter to `show_chat_dialog`, use it when provided, otherwise fall back to `get_active_project()`.

### 10. Semver versioning from pyproject.toml
Replace the git-commit-hash versioning (`get_version()` in `gui/utils.py`) with proper semver read from `pyproject.toml`. The version starts at `0.1.0`. The title bar shows `Worktree Control Center [v0.1.0]` and the bottom label shows `v0.1.0`. The `pyproject.toml` already has `version = "1.0.0"` — change it to `0.1.0`.

## Risks / Trade-offs

- **[Atlassian removal is irreversible in git history]** → Not a concern; there will be no Atlassian connection
- **[Settings dialog may look sparse]** → Acceptable; remaining tabs (Control Center, Git, Ralph, Notifications) are sufficient
- **[Archived changes lose historical context]** → Minimal risk; the changes are already archived and the context is preserved in the design docs
- **[docs-gen was useful for spec → docs]** → Can be rebuilt differently if needed; removing Confluence-specific tooling is the right call
- **[Gray default may not suit all users]** → Users can change theme in Settings; gray is the best middle ground
- **[Version bump to 0.1.0]** → Signals pre-1.0 status, appropriate for open-source launch
