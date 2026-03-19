## Context

OpenSpec skills contain "soft hooks" — prompt instructions telling the agent to run `set-memory recall` at the start and `set-memory remember` at the end of a skill session. These are unreliable because the agent can skip them when the task seems simple or when it jumps straight to action.

The existing hard hook infrastructure:
- `UserPromptSubmit` → `wt-hook-skill`: registers active skill in `.set-core/agents/<pid>.skill`
- `Stop` → `wt-hook-stop`: refreshes skill timestamp after each response

The Stop hook already fires after every agent response — it's the natural place to inject a reminder.

Claude Code hooks can output text to stdout, which gets injected back into the conversation as a `<user-prompt-submit-hook>` or similar system message. The agent sees this and is prompted to act on it.

## Goals / Non-Goals

**Goals:**
- Agent gets a system-level reminder to run memory recall/save when an active skill has memory hooks
- Zero configuration — works automatically for any skill with `set-memory` in its SKILL.md
- No performance impact — marker file check is a single `[ -f ]` test

**Non-Goals:**
- Auto-saving memories from the hook (impossible — hook has no conversation context)
- Guaranteeing 100% compliance (agent can still ignore the reminder, but it's much harder)
- Changing the SKILL.md memory instructions (they remain as-is for when the agent does follow them)

## Decisions

### Decision 1: Marker file (`.memory`) instead of re-parsing SKILL.md on every Stop

**Choice**: `wt-skill-start` checks the skill's SKILL.md for `set-memory` at registration time and writes a `.memory` marker. The Stop hook just checks `[ -f <pid>.memory ]`.

**Alternatives**:
- *Parse SKILL.md on every Stop*: Requires finding the skill dir, reading the file — too slow for a hook that fires on every response (should be <50ms)
- *Hardcode skill names that have memory*: Brittle, breaks when new skills are added

**Rationale**: One-time check at skill start, O(1) check on every Stop. The `.memory` file lives alongside `.skill` in `.set-core/agents/`.

### Decision 2: Reminder via stdout, not a separate mechanism

**Choice**: The Stop hook prints a reminder to stdout when `.memory` exists. Claude Code captures hook stdout and injects it into the conversation.

**Alternatives**:
- *Write to a file that the agent polls*: Agents don't poll files
- *Modify SKILL.md prompts to be more forceful*: Still a soft instruction

**Rationale**: stdout injection is the only way a shell hook can communicate back to the agent. It's already how Claude Code hooks work.

### Decision 3: Reminder on every Stop, not just the last one

**Choice**: The reminder is output on every Stop event while the skill is active.

**Alternatives**:
- *Only on first Stop*: Agent might not act on it immediately
- *Only on last Stop*: No way to know which Stop is the last one

**Rationale**: Repeated reminders increase compliance. The message is short (one line) and won't clutter the conversation. The agent can dismiss it if it has already handled memory.

### Decision 4: `wt-skill-start` handles marker creation

**Choice**: The existing `wt-skill-start` script (called by `wt-hook-skill` on UserPromptSubmit) also handles `.memory` marker creation/cleanup.

**Alternatives**:
- *Separate `set-memory-marker` script*: Adds complexity, another thing to install
- *Handle in `wt-hook-skill` directly*: Would need to know SKILL.md paths

**Rationale**: `wt-skill-start` already knows the skill name and can locate `.claude/skills/<skill-name>/SKILL.md`. Adding a grep for `set-memory` is trivial.

## Risks / Trade-offs

- **[Risk] Reminder fatigue**: Agent sees the reminder on every turn and starts ignoring it → Mitigation: Keep the message short and actionable. In practice, skills are 3-10 turns, so it's a handful of reminders.
- **[Risk] SKILL.md location detection**: `wt-skill-start` needs to find `.claude/skills/<skill>/SKILL.md` — the skill name may use `:` separators (e.g., `opsx:explore` → `.claude/skills/openspec-explore/SKILL.md`) → Mitigation: Map `opsx:*` → `openspec-*` prefix, `wt:*` → `wt` (single skill). This mapping already exists implicitly in the skill directory structure.
- **[Trade-off] Reminder is best-effort**: If the agent truly ignores it, memory still won't be saved → Accept: Going from ~80% to ~95% compliance is a meaningful improvement. 100% would require auto-saving, which is architecturally impossible from a shell hook.
