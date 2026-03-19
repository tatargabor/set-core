## Why

Agents currently save user-shared knowledge mid-flow and run self-reflection at session end, but they forget to save their OWN non-obvious discoveries at the moment of discovery. The pattern is: Discover → Summarize to user → forget to save. This was observed during a benchmark verification where the agent found a critical project-isolation gotcha in set-memory but only saved it after being prompted. The fix is to enforce a "Discover → Save → Tell" ordering in all relevant skills and in the CLAUDE.md ambient instruction.

## What Changes

- Add a "Save agent discoveries immediately" instruction block to all skills that perform investigation/verification: explore, apply, ff, continue, verify
- Update the CLAUDE.md proactive memory section to cover agent discoveries (not just user-shared knowledge)
- Establish "Discover → Save → Tell" as the canonical ordering pattern in all memory-related instructions
- Update the explore skill's mid-session memory section to explicitly include agent-discovered findings (not just user-shared knowledge)

## Capabilities

### New Capabilities
<!-- None — this is a behavioral fix across existing capabilities -->

### Modified Capabilities
- `ambient-memory`: Add agent self-discovery saving to the CLAUDE.md instruction (currently only covers user-shared knowledge)
- `explore-memory`: Add immediate agent discovery saving during exploration (currently only has session-end self-reflection and user-knowledge recognition)
- `midflow-memory`: Add agent discovery saving alongside existing user-knowledge recognition in apply/continue/ff
- `skill-memory-hooks`: Add "Discover → Save → Tell" ordering requirement to all skills with investigation phases

## Impact

- Modified files: CLAUDE.md (proactive memory section), all SKILL.md files that have memory hooks, all command .md files that have memory hooks
- No code changes to set-memory CLI, hooks, or GUI
- Behavioral change: agents will save discoveries immediately instead of deferring to session-end self-reflection
