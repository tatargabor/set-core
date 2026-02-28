## Context

The orchestrator decomposes specs into parallel changes. Dependencies are declared via `depends_on` arrays, but the decomposition prompt has minimal guidance about ordering. The only coded heuristic is "test infrastructure must be first." Everything else relies on Claude's general reasoning, which often misses semantic ordering patterns.

Current flow:
```
spec.md → decomposition prompt → Claude → changes[] with depends_on → validate → execute
```

The validation checks: valid JSON, kebab-case names, no dangling refs, no cycles, scope overlap (warn only). It does NOT check for missing ordering dependencies.

## Goals / Non-Goals

**Goals:**
- Plan-review skill suggests concrete `depends_on` annotations for spec items that have implicit ordering relationships
- Decomposition prompt includes explicit ordering heuristics (change-type classification)
- Spec-level dependency hints (`depends_on: ...`) are respected by the decomposition prompt

**Non-Goals:**
- Automated dependency injection without user review (too risky — could over-constrain parallelism)
- Post-decomposition LLM validation pass (too expensive for the benefit)
- Changes to the topological sort or dispatch logic (already correct — just needs better input)

## Decisions

### 1. Change-type taxonomy for ordering

Define 5 change types with a natural ordering:

```
infrastructure → schema → foundational → feature → cleanup-after
     ↓              ↓          ↓
  test setup    migrations   auth, shared types
```

Exception: **cleanup-before** (refactor, rename, reorganize) should run BEFORE features that touch the same area. This is the `ui-cleanup-pack` pattern.

The prompt will instruct Claude to classify each change and apply ordering:
- `infrastructure` — test setup, build config, CI → runs first
- `schema` — DB migrations, model changes → sequential, early
- `foundational` — auth, shared types, base components → before consumers
- `feature` — new functionality → bulk of parallel work
- `cleanup-before` — refactor/rename/reorganize → before features in same area
- `cleanup-after` — dead code removal, cosmetic fixes → after features

### 2. Prompt enrichment over post-validation

Adding heuristic rules to the prompt is simpler and cheaper than a second LLM call. Claude is capable of following explicit ordering rules when given them. The planning guide already documents these patterns — the gap is that they're not in the prompt.

### 3. Plan-review suggests, doesn't auto-fix

The `/wt:plan-review` skill will output a "Suggested Dependencies" section with concrete text to add to the spec. The user decides whether to apply them. This fits the existing review-then-fix workflow.

### 4. Spec-level dependency syntax

The spec already supports natural language dependencies (`depends_on: change-name`). The decomposition prompt will get an explicit instruction: "If the spec contains dependency annotations (e.g., 'depends_on: X'), preserve them in the output."

## Risks / Trade-offs

- **Over-constraining parallelism** — Too many ordering rules could serialize work that's actually safe in parallel. Mitigated by: rules are heuristics in the prompt, not hard constraints. Claude can override if the scopes genuinely don't overlap.
- **Prompt length** — Adding ~15 lines of ordering rules to the prompt. Minimal impact on token usage vs the benefit.
- **Cleanup-before detection** — Determining whether a cleanup change should run before vs after features requires understanding scope overlap, which is fuzzy. The plan-review skill handles this interactively; the planner prompt provides guidance but leaves the call to Claude.
