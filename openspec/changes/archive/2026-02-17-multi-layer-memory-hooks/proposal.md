## Why

The current memory hook system has two hooks (UserPromptSubmit recall, Stop save) but recall only fires on "change boundaries" (when a new OpenSpec change name is detected). This means: (1) explore mode gets no automatic recall because there's no change name, (2) intermediate steps like DB queries don't trigger recall even when relevant memories exist, (3) errors that were solved before get repeated because recall doesn't fire mid-conversation, and (4) without OpenSpec the hooks are nearly useless. Users have resorted to manually writing "always use wt:memory" in CLAUDE.md to force the agent to recall.

Additionally, every OpenSpec skill (apply, continue, ff, explore, archive, verify, sync, new) has inline `<!-- set-memory hooks -->` blocks that instruct the agent to manually call `set-memory recall` and `set-memory remember`. This is ~160 lines of duplicated memory instructions across 16 files (8 skills + 8 commands). These exist because the hooks don't cover enough of the lifecycle — if the hooks worked properly, the skills wouldn't need inline memory instructions at all.

Comparing with shodh-memory's reference implementation, they use 6 hook lifecycle events with `additionalContext` injection, and their CLAUDE.md simply states: "This is not a tool you query — it is part of how you think." The hooks handle everything; the agent uses `remember` only for emphasis. We need the same approach.

## What Changes

**BUILD — New hook scripts:**
- **New SessionStart hook** (L1): Loads a project-specific "operational cheat sheet" from memory at session start; also runs hot-topic discovery from project structure and memory tags
- **Rewrite UserPromptSubmit recall hook** (L2): Topic-based recall from prompt text instead of change-boundary detection; uses `additionalContext` JSON output; works without OpenSpec; zero benchmark-specific code
- **New PreToolUse hook** (L3): Pattern-matches Bash commands against discovered hot topics; runs synchronous recall; only fires on matching patterns, zero overhead otherwise
- **New PostToolUseFailure hook** (L4): Fires on Bash errors; parses error text as recall query; surfaces past fixes for the same error pattern
- **Enhanced Stop hook** (L5): Existing haiku transcript extraction stays; adds cheat-sheet promotion for convention/error-fix patterns
- **Updated wt-deploy-hooks**: Deploys all 5 hook types instead of 2; maintains `--no-memory` flag for baselines

**REMOVE — Inline memory instructions (hooks replace these):**
- All `<!-- set-memory hooks -->` blocks from 8 OpenSpec skills (apply, continue, ff, explore, archive, verify, sync, new)
- All `<!-- set-memory hooks -->` blocks from 8 opsx commands (same set)
- ~160 `set-memory` references across these files

**REWRITE — Project-level instructions:**
- **CLAUDE.md "Proactive Memory" section** → "Persistent Memory" (shodh-style): explain hooks handle recall/save automatically; agent uses `set-memory remember` only for emphasis; remove manual recall/save instructions
- **Hot topics**: Generic base patterns + project-discoverable extensions (from `bin/*`, project structure, memory tags) — no hardcoded project-specific patterns

## Capabilities

### New Capabilities
- `session-warmstart`: SessionStart hook that loads cheat-sheet memories + discovers project-specific hot topics
- `hot-topic-recall`: PreToolUse hook matching Bash commands against discovered hot-topic patterns, triggering synchronous memory recall
- `error-recovery-recall`: PostToolUseFailure hook that recalls memories on Bash errors for past fixes
- `cheat-sheet-curation`: L5 promotion of recurring patterns to persistent operational cheat sheet via tagging
- `hook-driven-memory`: Hooks handle ALL automatic memory operations; skills and CLAUDE.md no longer contain inline memory instructions

### Modified Capabilities
- `auto-memory-hooks-deploy`: Deploy script handles 4 new hook types (SessionStart, PreToolUse, PostToolUseFailure, enhanced Stop) alongside existing 2
- `smart-memory-recall`: Remove change-boundary limitation; switch to topic-based recall with `additionalContext` output; must work without OpenSpec; zero benchmark-specific code

## Impact

**New files:**
- **bin/wt-hook-memory-warmstart**: SessionStart hook (L1)
- **bin/wt-hook-memory-pretool**: PreToolUse hot-topic hook (L3)
- **bin/wt-hook-memory-posttool**: PostToolUseFailure error recovery hook (L4)

**Modified files:**
- **bin/wt-hook-memory-recall**: Full rewrite — topic-based recall with `additionalContext` JSON output
- **bin/wt-hook-memory-save**: Enhanced — cheat-sheet promotion, hot-topic auto-tagging
- **bin/wt-deploy-hooks**: Deploys all hook types
- **install.sh**: Symlinks new hook scripts
- **CLAUDE.md**: "Proactive Memory" → "Persistent Memory" rewrite

**Simplified files (memory hooks removed):**
- 8 skills: `openspec-{apply,continue,ff,explore,archive,verify,sync,new}-change/SKILL.md`
- 8 commands: `.claude/commands/opsx/{apply,continue,ff,explore,archive,verify,sync,new}.md`

**Documentation:**
- **docs/developer-memory.md**: Updated with 5-layer hook architecture docs

**Latency**: L3 adds ~150ms only on hot-topic Bash commands; all other Bash calls unaffected
**Dependencies**: No new external dependencies (uses existing set-memory CLI + shodh-memory server)
