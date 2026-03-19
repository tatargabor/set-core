## 1. CLI: set-memory-hooks HOOK_SKILLS expansion

- [ ] 1.1 Add `openspec-bulk-archive-change` to HOOK_SKILLS array in `bin/set-memory-hooks`
- [ ] 1.2 Add command file mapping for `bulk-archive-change` → `bulk-archive.md` in the COMMAND_MAP
- [ ] 1.3 Verify `set-memory-hooks check --json` reports correct `files_total: 9`
- [ ] 1.4 Check if existing manual hooks in bulk-archive SKILL.md use marker comments; if not, add markers so install/remove can manage them

## 2. SKILL.md: openspec-new-change explicit recall

- [ ] 2.1 Replace passive "Use injected memories" step 1b in `.claude/skills/openspec-new-change/SKILL.md` with explicit `set-memory health` + `set-memory recall` matching the command file pattern
- [ ] 2.2 Verify the patched SKILL.md loads correctly via Skill tool invocation

## 3. CLI: wt-deploy-hooks flag validation

- [ ] 3.1 Add unknown-flag validation to `bin/wt-deploy-hooks` — exit with error and usage message on unrecognized flags (e.g. `--memory`)

## 4. GUI: menu label clarification

- [ ] 4.1 Rename "Install Hooks" → "Install Claude Hooks" in worktree row context menu (`gui/control_center/mixins/menus.py:184`)
- [ ] 4.2 Rename "Install Memory Hooks..." → "Install Skill Memory Hooks..." in Memory submenu (`menus.py:323`)
- [ ] 4.3 Rename "Reinstall Memory Hooks..." → "Reinstall Skill Memory Hooks..." in Memory submenu (`menus.py:320`)
- [ ] 4.4 Rename "Install Memory Hooks..." → "Install Skill Memory Hooks..." in OpenSpec submenu (`menus.py:347`)
- [ ] 4.5 Rename "Reinstall Memory Hooks..." → "Reinstall Skill Memory Hooks..." in OpenSpec submenu (`menus.py:345`)
- [ ] 4.6 Update tooltip "Claude hooks not installed\nRight-click → Install Hooks" → "Claude hooks not installed\nRight-click → Install Claude Hooks" (`table.py:321`)

## 5. GUI: test updates

- [ ] 5.1 Update any existing GUI tests that assert on old menu label text (search for "Install Hooks", "Install Memory Hooks" in `tests/gui/`)
- [ ] 5.2 Add test verifying "Install Claude Hooks" label appears in worktree context menu when hooks_installed is False
- [ ] 5.3 Add test verifying "Install Skill Memory Hooks..." label appears in Memory submenu when hooks not installed
