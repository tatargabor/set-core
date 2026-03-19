## Why

The bulk-archive skill (both SKILL.md and command file) is missing `set-memory` hooks that all other stateful OpenSpec skills already have. The regular archive skill saves completion context, decisions, and learnings per change — but the bulk version, which archives multiple changes at once, saves nothing. This is a gap: bulk archiving produces even richer context (conflict resolutions, batch-level patterns) that should be captured.

## What Changes

- Add **Agent Self-Reflection** memory hooks to the bulk-archive skill, adapted for batch operations:
  - Per-change completion context (same as regular archive)
  - Batch-level conflict resolution decisions
  - Batch-level learnings
- Add **mid-flow user-knowledge recognition** hook (same pattern as other skills)
- Add **memory recall** at the start (check for relevant past experience before processing)
- Apply changes to **both** SKILL.md and command file (dual-file architecture)

## Capabilities

### New Capabilities

_(none — this adds memory hooks to an existing skill, not a new capability)_

### Modified Capabilities

_(no spec-level requirement changes — this is a skill prompt enhancement, not a behavioral requirement change)_

## Impact

- **Files modified**:
  - `.claude/skills/openspec-bulk-archive-change/SKILL.md`
  - `.claude/commands/opsx/bulk-archive.md`
- **No code changes**: This is purely prompt/skill file edits
- **No breaking changes**: Existing bulk-archive behavior is preserved; memory hooks are additive and gracefully degrade (skip silently if `set-memory health` fails)
