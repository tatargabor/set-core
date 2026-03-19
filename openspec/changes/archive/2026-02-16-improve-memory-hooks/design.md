## Context

Two bash hook scripts (`bin/wt-hook-memory-save` and `bin/wt-hook-memory-recall`) auto-save and auto-recall memories via `set-memory` during autonomous agent sessions. They run as Claude Code settings.json hooks (Stop and UserPromptSubmit events). Currently they produce verbose, redundant memories that don't effectively help the agent.

## Goals / Non-Goals

**Goals:**
- One concise memory per change (~200 chars) with only key technical choices
- Smart recall that queries by pending OpenSpec change names, not raw prompt text
- Actionable recall output format that tells the agent what to maintain consistency with

**Non-Goals:**
- Changing the set-memory CLI itself
- Changing the hook registration in settings.json (same commands, same timeouts)
- Agent-initiated memory saves (that's a separate concern)

## Decisions

### 1. Extract only **Choice** lines from design.md
**Choice**: Use `grep '^\*\*Choice\*\*'` to pull just the decision lines, strip markdown formatting, join into a single compact string prefixed with the change name.
**Rationale**: The **Choice** line is the only actionable part. Rationale and risk sections are useful for humans but not for agent recall at 300-char truncation.

### 2. One memory per change instead of three
**Choice**: Save a single Decision-type memory combining change name + condensed choices. Drop separate Context (commit msg) and Learning (goals) memories.
**Rationale**: The commit message duplicates the change name. The goals list duplicates the proposal. One condensed memory is more useful than three verbose ones.

### 3. Recall by OpenSpec pending changes
**Choice**: In the recall hook, run `openspec list --json` to find changes with incomplete status, then recall memories tagged with completed change names.
**Rationale**: The prompt text in wt-loop is always the same generic task. What matters is which changes are done (recall their decisions) and which are pending (that's what the agent will work on next).

### 4. Actionable recall output format
**Choice**: Format recall output as a bulleted list of "change-name: key decisions" with a header instructing the agent to maintain consistency.
**Rationale**: Raw JSON memory dumps with tags are noise for the agent. A clean summary is more likely to influence behavior.

## Risks / Trade-offs

- [grep-based extraction] → Brittle if design.md format varies. Acceptable because OpenSpec templates enforce consistent format.
- [openspec list dependency] → Recall hook now requires openspec CLI. Falls back gracefully (exit 0) if not available.
- [Single memory per change] → Less granular than 3 memories. But granularity wasn't useful at current recall quality.
