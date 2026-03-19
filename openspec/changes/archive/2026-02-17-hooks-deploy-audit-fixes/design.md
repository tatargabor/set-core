## Context

The hook/deploy infrastructure has two parallel invocation paths for OpenSpec skills:
1. **Skill tool path** — LLM calls Skill tool → `.claude/skills/<name>/SKILL.md` loaded
2. **Command path** — User types `/opsx:<id>` → `.claude/commands/opsx/<id>.md` loaded

Memory integration uses two strategies across these paths:
- **Hook-injected** (SKILL.md): relies on `wt-hook-memory-recall` to inject `=== PROJECT MEMORY ===` block on change boundaries; skill says "if you see it, use it"
- **Explicit recall** (command files): skill calls `set-memory recall` directly in a step

Both are valid. The audit found these have drifted in some places, and the GUI labels are ambiguous about which hook system each action installs.

## Goals / Non-Goals

**Goals:**
- All skills managed by `set-memory-hooks install`/`check`/`remove` consistently
- GUI labels clearly distinguish Claude Code hooks (settings.json) from skill memory hooks (SKILL.md patches)
- `wt-deploy-hooks` rejects invalid flags with usage message
- Tooltips guide users to the right action

**Non-Goals:**
- Unifying SKILL.md and command file memory strategies (hook-injected vs explicit — both work)
- Adding memory hooks to `openspec-onboard` (intentionally excluded — onboarding is a one-time walkthrough)
- Adding unit tests for hook scripts (separate change scope)

## Decisions

**Choice: Add `openspec-bulk-archive-change` to HOOK_SKILLS only (not onboard)**
- bulk-archive was manually patched outside `set-memory-hooks` scope — brings it under management
- onboard excluded by user decision: one-time walkthrough, not a recurring workflow
- Alternative considered: add both → rejected, onboard doesn't benefit from memory integration

**Choice: Align `openspec-new-change/SKILL.md` with command file recall pattern**
- Currently SKILL.md step 1b says "Use injected memories" (passive hook-based)
- Command file step 1b has explicit `set-memory recall` call
- Both work, but explicit is more reliable (doesn't depend on change-boundary detection timing)
- Will add explicit recall to SKILL.md step 1b to match command file
- Alternative considered: leave as-is since hook works → rejected for consistency

**Choice: GUI label rename pattern**
- Worktree row context menu: "Install Hooks" → "Install Claude Hooks" (deploys `wt-deploy-hooks` → settings.json)
- Memory submenu: "Install Memory Hooks..." → "Install Skill Memory Hooks..." (runs `set-memory-hooks install` → SKILL.md patches)
- Memory submenu: "Reinstall Memory Hooks..." → "Reinstall Skill Memory Hooks..."
- OpenSpec submenu: same rename pattern as Memory submenu
- Tooltip: "Claude hooks not installed\nRight-click → Install Hooks" → "Claude hooks not installed\nRight-click → Install Claude Hooks"
- Alternative considered: "Deploy Hooks" vs "Patch Skills" → rejected, too jargon-heavy

**Choice: Add unknown-flag validation to `wt-deploy-hooks`**
- `wt-deploy-hooks` currently silently ignores invalid flags (e.g. `--memory`)
- Add flag parsing that exits with error + usage on unrecognized flags
- This protects all consumers (scripts, GUI, manual invocation) from silent misconfiguration
- Alternative considered: add `--memory` as an explicit alias → rejected, memory is already the default; adding redundant flags creates confusion

## Risks / Trade-offs

- [Label change breaks muscle memory] → Low risk, labels are menu items users scan visually, not typed
- [SKILL.md explicit recall duplicates hook recall] → Both may fire in same session; the explicit recall is a no-op if hook already injected memories. Acceptable overlap.
- [set-memory-hooks install overwrites manual bulk-archive patches] → set-memory-hooks uses marker-based patching (`<!-- set-memory hooks start/end -->`); if manual patches lack markers, install may add a second copy. Will verify manual patches use markers; if not, align them first.
