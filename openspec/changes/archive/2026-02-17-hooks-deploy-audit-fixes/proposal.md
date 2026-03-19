## Why

An audit of the hook/deploy infrastructure found drift between source, CLI, and GUI:
- `openspec-new-change/SKILL.md` has zero memory hooks while its command counterpart (`new.md`) does — the Skill-tool path silently skips memory recall
- `set-memory-hooks` HOOK_SKILLS array lists 8 skills but `openspec-bulk-archive-change` was manually patched outside its scope
- `wt-deploy-hooks` silently accepts invalid flags (e.g. `--memory`) instead of erroring — consumers can pass wrong flags without knowing
- GUI menu labels ("Install Hooks" vs "Install Memory Hooks...") don't clearly communicate what each action deploys

## What Changes

- Patch `openspec-new-change/SKILL.md` with memory recall hook matching its command file counterpart
- Add `openspec-bulk-archive-change` to `set-memory-hooks` HOOK_SKILLS array so `install`/`check`/`remove` manage it properly
- Add unknown-flag validation to `wt-deploy-hooks` so invalid flags (like `--memory`) cause an error with usage
- Clarify GUI menu labels:
  - "Install Hooks" (worktree context menu) → "Install Claude Hooks" to distinguish from memory hooks
  - "Install Memory Hooks..." → "Install Skill Memory Hooks..." to clarify it patches SKILL.md, not settings.json
  - Matching tooltip updates
- Verify all GUI hook/deploy actions are present and functional

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `memory-hooks-cli`: Add `openspec-bulk-archive-change` to HOOK_SKILLS array
- `memory-hooks-gui`: Clarify menu labels to distinguish Claude Code hooks from skill-level memory hooks
- `hook-auto-install`: Add unknown-flag validation to `wt-deploy-hooks`

## Impact

- `bin/set-memory-hooks` — HOOK_SKILLS array change
- `.claude/skills/openspec-new-change/SKILL.md` — add memory recall block
- `bin/wt-deploy-hooks` — add flag validation
- `gui/control_center/mixins/menus.py` — label text changes
- `gui/control_center/mixins/table.py` — tooltip text changes
- No breaking changes, no new dependencies
