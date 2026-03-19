## Context

Memory hooks in OpenSpec skills currently only fire at workflow endpoints (apply step 7, archive step 7). The `/opsx:explore` skill has no memory integration at all. Users share valuable knowledge conversationally throughout sessions — corrections, past experiences, technical gotchas — and this knowledge is lost. The shodh-memory service is running and the `set-memory` CLI works, but nothing triggers saves mid-conversation.

## Goals / Non-Goals

**Goals:**
- Memory saves happen when valuable knowledge is shared, not just at ceremony points
- Works regardless of user's language (Hungarian, English, mixed)
- Minimal disruption to conversation flow (brief confirmations, silent recalls)
- No duplicate saves (skill hooks and CLAUDE.md don't conflict)

**Non-Goals:**
- Building a classifier or NLP model for intent detection — we rely on Claude's native understanding
- Saving everything — quality over quantity, only genuinely valuable insights
- Changing the shodh-memory API or storage format
- Adding GUI elements (this is purely agent-side behavior)

## Decisions

### 1. Claude's native understanding over keyword matching
Claude is inherently multilingual and understands semantic intent. Instead of pattern matching ("we tried" → remember), the SKILL.md instructions describe the INTENT to recognize: "when the user shares a negative past experience with a technology or approach." Claude handles Hungarian, English, German, mixed-language equally well.

Alternative considered: Regex/keyword detection in bash hooks — rejected because it's language-dependent and can't access conversation context.

### 2. SKILL.md instructions over bash hooks
Memory recognition must happen inside the LLM context where the agent has full conversation history. Bash hooks (PreToolUse/PostToolUse) only see tool calls, not user messages. Therefore all proactive memory logic is expressed as natural-language instructions in SKILL.md files and CLAUDE.md.

### 3. "Save immediately, confirm briefly" pattern
When the agent recognizes something worth saving, it:
1. Runs `set-memory health` (skip if fails)
2. Runs `echo "..." | set-memory remember --type X --tags ...`
3. Shows one-line confirmation: `[Memory saved: Type — summary]`
4. Continues with current work

This is fast (~50ms health + ~100ms remember) and doesn't break flow.

### 4. Deduplication via skill awareness
The CLAUDE.md ambient instruction includes: "If you are currently executing an OpenSpec skill that has its own memory hooks (check for set-memory steps in the active skill), defer to those hooks — do not save duplicates." This prevents double-saves when both CLAUDE.md and SKILL.md try to remember.

### 5. Hook content in set-memory-hooks script
The new explore hooks and mid-flow hooks are added to `set-memory-hooks install`, so `openspec update` + `set-memory-hooks install` restores everything. The CLAUDE.md section is NOT managed by `set-memory-hooks` — it's a stable project-level instruction.

### 6. Save threshold: "would a future agent benefit?"
The heuristic for deciding whether to save: "Would this information be valuable to a different agent working on this project in a future session?" This filters out session-specific noise ("fix this typo", "run tests") while capturing durable knowledge ("this API breaks on empty arrays", "always use --force").

## Risks / Trade-offs

- **Over-saving risk**: Agent might save too aggressively, creating noise in memory. → Mitigation: Clear threshold in instructions + SKILL.md examples of what NOT to save.
- **Under-saving risk**: Agent might not recognize non-English knowledge patterns. → Mitigation: Instructions describe intent, not phrases. Claude's multilingual understanding handles this natively.
- **Confirmation fatigue**: Users might find `[Memory saved: ...]` lines annoying if too frequent. → Mitigation: Threshold ensures saves are rare (only genuinely valuable), and confirmations are one line.
- **Deduplication isn't perfect**: CLAUDE.md instruction says "defer to skill hooks" but there's no enforcement mechanism. → Mitigation: Worst case is a duplicate memory, which is low cost.
