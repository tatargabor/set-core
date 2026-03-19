## Context

The memory system has three save triggers: (1) user-shared knowledge mid-flow, (2) agent self-reflection at session end, and (3) phase-specific saves in apply/verify/archive. There is a gap: when an agent discovers something non-obvious during investigation (running commands, reading code, verifying behavior), it summarizes findings to the user but does not save them as memory. The session-end self-reflection COULD catch this, but in practice agents often skip or forget it — especially in explore mode where there's no structured "end" step.

The root cause is an ordering problem. The current implicit flow is:

```
Discover → Tell user → (maybe save at session end)
```

The fix is to make the ordering explicit:

```
Discover → Save → Tell user
```

## Goals / Non-Goals

**Goals:**
- Ensure agent-discovered insights are saved immediately, at the moment of discovery
- Establish "Discover → Save → Tell" as a named, referenceable pattern
- Minimize added text — a short rule, not paragraphs of instruction
- Cover both skill-driven and ambient (CLAUDE.md) contexts

**Non-Goals:**
- Changing the recall system (recall works fine)
- Adding new memory types or tags
- Changing the session-end self-reflection (keep it as a safety net)
- Modifying set-memory CLI or hooks infrastructure

## Decisions

### D1: Add a single "Discover → Save → Tell" rule, not per-skill instructions

**Decision**: Add one concise instruction block that applies everywhere, rather than duplicating detailed instructions in each skill. Skills reference the pattern by name.

**Why**: The problem is not that skills lack instructions — it's that the ordering isn't explicit. Adding more text per skill increases cognitive load and doesn't fix the core issue. A named pattern ("Discover → Save → Tell") is memorable and referenceable.

**Instruction text** (approximately):
```
### Agent Discovery Saving

When you discover something non-obvious during investigation (running commands,
reading code, testing behavior), save it BEFORE summarizing to the user.

Order: Discover → Save → Tell
Not: Discover → Tell → (forget to save)

What counts: gotchas, unexpected behavior, architecture findings,
environment quirks, things a future agent would hit.
What doesn't: routine observations, things already in docs/specs.
```

### D2: Add to CLAUDE.md ambient section AND to investigation-heavy skills

**Decision**: The rule goes in two places:
1. CLAUDE.md proactive memory section (covers all contexts)
2. Explore, FF, and Apply SKILL.md files (the skills where agents most often investigate)

**Why**: CLAUDE.md covers ambient sessions. But during skills, agents focus on skill instructions and may not re-read CLAUDE.md behavior. The skill-level addition is a reminder, not a duplication — just a one-liner referencing the pattern.

### D3: Keep session-end self-reflection as safety net

**Decision**: Don't remove the existing session-end self-reflection. It stays as a catch-all for anything missed during the session.

**Why**: Belt and suspenders. Immediate saving is the primary mechanism; session-end reflection catches anything that slipped through.

## Risks / Trade-offs

**[Risk: Over-saving]** → Agents might save trivial findings to comply with the rule. **Mitigation**: The "what counts" criteria is explicit: non-obvious findings only. "Routine observations" are excluded.

**[Risk: Interrupts flow]** → Saving before telling might feel disruptive. **Mitigation**: The save is a single `set-memory remember` call + one-line confirmation. Takes <2 seconds. The tell comes right after.
