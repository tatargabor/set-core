## 1. Hook Script

- [x] 1.1 Create `bin/wt-hook-stop` script that reads `.set-core/current_skill`, refreshes its timestamp if present, exits 0 silently otherwise

## 2. Install Script Updates

- [x] 2.1 Add `wt-skill-start` and `wt-hook-stop` to the scripts list in `install_scripts()` in `install.sh`
- [x] 2.2 Create `install_project_hooks()` function in `install.sh` that reads `projects.json` and merges Stop hook config into each project's `.claude/settings.json` (using jq, same pattern as `install_mcp_statusline()`)
- [x] 2.3 Add `install_project_hooks` call to `main()` in `install.sh`

## 3. wt-add Hook Deployment

- [x] 3.1 Add hook deployment to `wt-add` so new projects get `.claude/settings.json` with Stop hook after registration

## 4. SKILL.md Updates

- [x] 4.1 Add `wt-skill-start <skill-name>` to all opsx SKILL.md files that don't have it (`openspec-apply-change`, `openspec-archive-change`, `openspec-bulk-archive-change`, `openspec-continue-change`, `openspec-explore`, `openspec-ff-change`, `openspec-new-change`, `openspec-onboard`, `openspec-sync-specs`, `openspec-verify-change`)

## 5. Verification

- [x] 5.1 Run `install.sh` and verify `wt-skill-start` and `wt-hook-stop` are symlinked to `~/.local/bin/`
- [x] 5.2 Verify `.claude/settings.json` is created/updated for registered projects with Stop hook
- [x] 5.3 Test end-to-end: start a skill, confirm `wt-status --json` shows skill name, wait for Stop hook to fire, confirm timestamp refreshes
