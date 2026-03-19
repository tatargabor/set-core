## Context

The regular archive skill (`openspec-archive-change`) has three memory hooks:
1. **Recall** at start — checks for relevant past experience
2. **Mid-flow user-knowledge recognition** — saves user corrections/decisions during execution
3. **Agent self-reflection** at end — saves decisions, learnings, and completion context

The bulk-archive skill was created before the memory integration and has none of these hooks. Both the SKILL.md and command file need identical updates (dual-file architecture).

## Goals / Non-Goals

**Goals:**
- Add all three memory hook categories to bulk-archive, adapted for batch operations
- Maintain consistency with the regular archive skill's memory patterns
- Ensure both SKILL.md and command file are updated identically

**Non-Goals:**
- Changing bulk-archive's core behavior (selection, conflict resolution, archiving)
- Adding memory hooks to other skills (already done)
- Modifying the set-memory CLI tool itself

## Decisions

### 1. Per-change vs batch-level memory saves

**Decision**: Use a hybrid approach — per-change completion context + batch-level decisions/learnings.

**Rationale**: The regular archive saves per-change context. In bulk mode, each archived change still deserves its own completion record (so future agents can look up any individual change). But conflict resolutions and process learnings are batch-level concepts that don't belong to any single change.

**Alternative considered**: Only batch-level summary → loses per-change granularity that memory recall depends on.

### 2. Where to insert the memory hooks

**Decision**: Follow the same structural pattern as the regular archive:
- Recall: after step 1 (get active changes), before step 2 (prompt for selection)
- Mid-flow recognition: as an ongoing hook described after the recall step
- Self-reflection: as the final step after "Display summary" (step 9)

**Rationale**: Consistent placement across skills makes the pattern predictable and maintainable.

### 3. Tag schema for batch memories

**Decision**: Use `phase:bulk-archive` (not `phase:archive`) to distinguish from single-archive memories. Per-change completions use `change:<name>` tag. Batch-level insights use `change:bulk-<date>` or just omit the change tag.

**Rationale**: Allows memory recall to filter specifically for bulk-archive experiences vs single-archive ones when relevant.

## Risks / Trade-offs

- **[Risk] Many memory writes in one session** (N changes × completion + batch insights) → Mitigation: per-change completions are one-liners; this is bounded by the number of archived changes which is typically small (2-5).
- **[Risk] Dual-file drift** — editing SKILL.md and command file separately could lead to divergence → Mitigation: tasks.md will list both files explicitly. Apply step will edit both in sequence.
