## Context

The project has a `/wt:memory` slash command (`.claude/commands/wt/memory.md`) that provides interactive memory access. The `remember` subcommand asks for type and tags — too slow for quick capture. We need a separate `/wt:todo` command that's fire-and-forget.

The project already has `wt-memory recall --tags-only --tags <tags>` (just implemented in proactive-context-and-cli-enhancements) for fast tag-based lookups, and `wt-memory forget <id>` for deletion.

## Goals / Non-Goals

**Goals:**
- One-shot todo capture: `/wt:todo <text>` → saved, done
- Retrievable list: `/wt:todo list` shows all open todos
- Completable: `/wt:todo done <id>` removes a todo
- Auto-tagging with current change context

**Non-Goals:**
- Priority levels, categories, or due dates (keep it simple)
- Separate storage — uses existing shodh-memory
- Editing todos — just delete and re-create
- Status tracking beyond open/done (no "in progress")

## Decisions

### D1: Slash command, not CLI extension
**Decision**: Create `.claude/commands/wt/todo.md` (a slash command prompt) rather than adding a `wt-memory todo` CLI subcommand.
**Rationale**: The user explicitly wants this as a skill invocation (`/wt:todo`). Slash commands are agent instructions — they tell the agent what to do. The agent then uses existing `wt-memory` CLI commands to execute. No new CLI code needed.

### D2: Auto-detect current change from openspec
**Decision**: The slash command instructs the agent to detect the current active change (from conversation context or `openspec list --json`) and add `change:<name>` tag.
**Rationale**: This makes todos discoverable per-change and lets `proactive_context()` surface them when working on that change. Falls back gracefully — if no change detected, just skip the tag.

### D3: Use existing wt-memory commands for all operations
**Decision**: Save = `echo | wt-memory remember`, List = `wt-memory recall --tags-only --tags todo`, Done = `wt-memory forget <id>`.
**Rationale**: Zero new code in `bin/wt-memory`. All functionality already exists. The slash command is pure orchestration.

### D4: Agent must not pursue todo content
**Decision**: The slash command explicitly instructs: "After saving, continue with your current task. Do NOT act on or discuss the todo content."
**Rationale**: This is the core requirement. Without explicit instruction, the agent would naturally try to help with whatever the user mentioned.

## Risks / Trade-offs

- **[Risk] Todos mixed with regular memories**: Tagged memories could show up in unrelated recalls.
  → Mitigation: The `todo` tag makes them distinguishable. The `proactive_context()` relevance scoring helps — todos only surface when contextually relevant.

- **[Trade-off] No persistent state beyond memory**: If shodh-memory is cleared, todos are lost.
  → Acceptable: todos are lightweight ideas, not commitments. The sync feature backs them up.
