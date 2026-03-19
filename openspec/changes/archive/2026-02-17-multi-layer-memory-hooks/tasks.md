## 1. L1 — SessionStart Warmstart Hook

- [x] 1.1 Create `bin/wt-hook-memory-warmstart` script: health check → recall cheat-sheet tagged memories → proactive context from project name + recent git files → output JSON with `hookSpecificOutput.additionalContext`
- [x] 1.2 Add hot-topic discovery: scan `bin/*` for command prefixes, check `package.json`/`Makefile`/`pyproject.toml` for project tools, query frequent memory tags → write `.claude/hot-topics.json` cache
- [x] 1.3 Add `wt-hook-memory-warmstart` to symlink list in `install.sh` (also added pretool + posttool)

## 2. L2 — Rewrite UserPromptSubmit Recall Hook

- [x] 2.1 Rewrite `bin/wt-hook-memory-recall`: remove ALL change-boundary detection, debounce, benchmark-specific case statements; extract topic from prompt text; detect opsx/openspec skill names and change names; always recall using `set-memory proactive` or `set-memory recall`
- [x] 2.2 Switch output from plain text stdout to JSON `hookSpecificOutput.additionalContext` format
- [x] 2.3 Keep `=== PROJECT MEMORY ===` prefix in the additionalContext text for readability in context

## 3. L3 — PreToolUse Hot-Topic Hook

- [x] 3.1 Create `bin/wt-hook-memory-pretool` script: parse `tool_input.command` from stdin JSON; load `.claude/hot-topics.json` + generic base patterns; single regex check; exit 0 immediately on no match
- [x] 3.2 On hot-topic match: use matched command as recall query → `set-memory recall` → output JSON `hookSpecificOutput.additionalContext` with max 2 memories
- [x] 3.3 Add `wt-hook-memory-pretool` to symlink list in `install.sh`

## 4. L4 — PostToolUseFailure Error Recovery Hook

- [x] 4.1 Create `bin/wt-hook-memory-posttool` script: parse `error` and `is_interrupt` from stdin JSON; skip if `is_interrupt` is true; skip if error text < 10 chars
- [x] 4.2 Use first 300 chars of error text as recall query → `set-memory recall` with limit 3 → output JSON `hookSpecificOutput.additionalContext` prefixed with `=== MEMORY: Past fix for this error ===`
- [x] 4.3 Auto-promote failed command to hot topic: extract command prefix from `tool_input.command`; skip trivial commands (ls, cat, echo, cd, etc.); append pattern to `.claude/hot-topics.json` `promoted` array so L3 catches it on next Bash call in same session
- [x] 4.4 Add `wt-hook-memory-posttool` to symlink list in `install.sh`

## 5. L5 — Enhanced Stop Hook (Cheat Sheet Curation)

- [x] 5.1 Update haiku extraction prompt in `bin/wt-hook-memory-save`: add `CheatSheet` type alongside existing `Learning|Decision|Context|Convention`; instruct haiku to use CheatSheet for reusable operational patterns
- [x] 5.2 In the commit-staged-files parsing loop: map `CheatSheet` type to `Learning` with `cheat-sheet` tag; auto-add `cheat-sheet` tag to `Convention` entries too; cap CheatSheet entries at 2 per session

## 6. Deploy Script Update

- [x] 6.1 Update `bin/wt-deploy-hooks`: add `SessionStart` entry with `wt-hook-memory-warmstart` (timeout 10), `PreToolUse` entry matching `"Bash"` with `wt-hook-memory-pretool` (timeout 5), `PostToolUseFailure` entry matching `"Bash"` with `wt-hook-memory-posttool` (timeout 5)
- [x] 6.2 Add upgrade path: detect existing configs with old 2-hook memory setup → add new 3 hooks while preserving existing entries
- [x] 6.3 Ensure `--no-memory` flag skips all 5 memory hooks (not just the original 2)

## 7. Remove Inline Memory Hooks from Skills

- [x] 7.1 Remove all `<!-- set-memory hooks -->` blocks from `openspec-apply-change/SKILL.md` (hooks, hooks-midflow, hooks-remember)
- [x] 7.2 Remove all `<!-- set-memory hooks -->` blocks from `openspec-continue-change/SKILL.md` (hooks, hooks-midflow, hooks-reflection)
- [x] 7.3 Remove all `<!-- set-memory hooks -->` blocks from `openspec-ff-change/SKILL.md` (hooks, hooks-midflow, hooks-reflection)
- [x] 7.4 Remove all `<!-- set-memory hooks -->` blocks from `openspec-explore/SKILL.md` (hooks, hooks-remember, hooks-reflection)
- [x] 7.5 Remove all `<!-- set-memory hooks -->` blocks from `openspec-archive-change/SKILL.md` (hooks)
- [x] 7.6 Remove all `<!-- set-memory hooks -->` blocks from `openspec-verify-change/SKILL.md` (hooks, hooks-save)
- [x] 7.7 Remove all `<!-- set-memory hooks -->` blocks from `openspec-sync-specs/SKILL.md` (hooks)
- [x] 7.8 Remove all `<!-- set-memory hooks -->` blocks from `openspec-new-change/SKILL.md` (hooks)

## 8. Remove Inline Memory Hooks from Commands

- [x] 8.1 Remove all `<!-- set-memory hooks -->` blocks from `.claude/commands/opsx/apply.md`
- [x] 8.2 Remove all `<!-- set-memory hooks -->` blocks from `.claude/commands/opsx/continue.md`
- [x] 8.3 Remove all `<!-- set-memory hooks -->` blocks from `.claude/commands/opsx/ff.md`
- [x] 8.4 Remove all `<!-- set-memory hooks -->` blocks from `.claude/commands/opsx/explore.md`
- [x] 8.5 Remove all `<!-- set-memory hooks -->` blocks from `.claude/commands/opsx/archive.md`
- [x] 8.6 Remove all `<!-- set-memory hooks -->` blocks from `.claude/commands/opsx/verify.md`
- [x] 8.7 Remove all `<!-- set-memory hooks -->` blocks from `.claude/commands/opsx/sync.md`
- [x] 8.8 Remove all `<!-- set-memory hooks -->` blocks from `.claude/commands/opsx/new.md`

## 9. CLAUDE.md & Documentation Updates

- [x] 9.1 Rewrite CLAUDE.md "Proactive Memory" section → "Persistent Memory" (shodh-style): hooks handle everything, agent uses `remember` for emphasis only, remove manual recall/save instructions, remove deduplication note
- [x] 9.2 Update `docs/developer-memory.md`: add section describing all 5 hook layers (L1–L5) with diagram showing when each fires
- [x] 9.3 Update `docs/developer-memory.md`: document hot-topic discovery mechanism, cache file format, generic base patterns
- [x] 9.4 Update `docs/developer-memory.md`: document the "hooks replace skill instructions" architecture decision

## 10. Integration Testing

- [x] 10.1 Test L1: verify SessionStart hook loads cheat-sheet memories, discovers hot topics, writes cache file, outputs valid JSON
- [x] 10.2 Test L2: verify recall fires on plain prompts, opsx:explore topics, and opsx:ff change names; verify additionalContext JSON format; verify no benchmark-specific code paths
- [x] 10.3 Test L3: verify hot-topic matching from cache file; verify generic base patterns; verify additionalContext injection; measure latency for non-matching commands
- [x] 10.4 Test L4: verify PostToolUseFailure recall on error text; verify is_interrupt skip; verify additionalContext format
- [x] 10.5 Test L5: verify CheatSheet type extraction and cheat-sheet tag promotion
- [x] 10.6 Test deploy: verify fresh deploy creates all 5 hook entries; verify upgrade from old 2-hook config; verify --no-memory skips all
- [x] 10.7 Test skill files: verify no remaining `set-memory` references in skill/command memory hook blocks; verify skills still work without inline memory hooks

## 11. Deprecate `set-memory-hooks install` & Auto-Remove in Deploy

- [x] 11.1 Update `bin/set-memory-hooks`: `cmd_install()` → print deprecation warning and exit (no-op); keep `check` and `remove` working
- [x] 11.2 Update `bin/set-project`: add `set-memory-hooks remove --quiet` call in `deploy_set_tools()` after hooks deploy
- [x] 11.3 Add `--quiet` flag to `set-memory-hooks remove` (suppress per-file output, only show summary or nothing)

## 12. GUI Cleanup — Remove Inline Hook Install UI

- [x] 12.1 `gui/control_center/mixins/menus.py`: remove "Install/Reinstall Memory Hooks..." from Memory menu (lines 314-324)
- [x] 12.2 `gui/control_center/mixins/menus.py`: remove "Install/Reinstall Memory Hooks..." from OpenSpec menu (lines 341-348)
- [x] 12.3 `gui/control_center/mixins/menus.py`: remove `_run_memory_hooks_install()` method
- [x] 12.4 `gui/control_center/mixins/menus.py`: remove auto-reinstall logic from `_run_openspec_action()` (lines 423-435)
- [x] 12.5 `gui/control_center/mixins/table.py`: remove `hooks_installed` tooltip (line 208-209) and warning emoji (line 316-317)
- [x] 12.6 `gui/workers/feature.py`: remove `_poll_memory_hooks()` method and hooks check from `_poll_project()` (lines 79-82)

## 13. Test Updates

- [x] 13.1 Delete `tests/gui/test_26_hooks_indicator.py` (entire file — tests inline hook install/warning UI that no longer exists)
- [x] 13.2 Update `tests/gui/test_29_memory.py`: remove `hooks_installed` from test data and update `test_memory_button_hooks_installed_tooltip` test
- [x] 13.3 Update `tests/gui/test_30_openspec_button.py`: remove `test_feature_worker_has_memory_hooks_poll` test

## 14. Documentation & Spec Updates

- [x] 14.1 Update `docs/developer-memory.md`: remove `set-memory-hooks install` from CLI reference and setup flows; document that deploy handles inline removal automatically
- [x] 14.2 Update `README.md`: update CLI table — remove install row, update check/remove descriptions
- [x] 14.3 Update `docs/readme-guide.md`: update CLI list reference
- [x] 14.4 Update main specs: mark `openspec/specs/memory-hooks-cli/spec.md` and `openspec/specs/memory-hooks-gui/spec.md` as deprecated (install command superseded by 5-layer hooks)
