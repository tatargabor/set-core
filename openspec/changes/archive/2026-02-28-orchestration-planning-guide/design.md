## Context

The orchestrator (`set-orchestrate`) takes a spec document or project brief, decomposes it into changes via an LLM call, and executes them in parallel worktrees. Plan quality directly determines batch success — yet users have no documentation on how to write effective inputs. The existing `docs/orchestration.md` covers CLI usage but not planning strategy. The Hungarian PM guide (`docs/pm-guide/05-orchestracio.md`) covers workflow but not input authoring best practices.

Real-world failure patterns observed:
- Overlapping change scopes causing merge conflicts (e.g., multiple changes editing `activity-logger.ts` union types)
- Missing dependency declarations leading to build failures after merge
- Overly large changes that stall or produce low-quality code
- Missing test requirements leading to untested features
- Generated file conflicts (`.claude/reflection.md`) blocking merges
- Post-merge dependency gaps (new packages not installed on main)

## Goals / Non-Goals

**Goals:**
- Provide a single reference document for writing effective orchestration plans
- Include a quick-reference checklist for plan review before execution
- Cover web-project-specific patterns (DB, auth, API, persistence, deployment)
- Explain plan sizing and splitting strategies
- Document design rules: what to specify vs what to leave to the agent

**Non-Goals:**
- Changing the orchestrator's code or plan decomposition prompt
- Replacing the existing `docs/orchestration.md` CLI guide
- Covering OpenSpec workflow mechanics (that's in the PM guide)

## Decisions

### 1. Single guide document + separate checklist
**Decision**: Create `docs/planning-guide.md` as the comprehensive guide and `docs/plan-checklist.md` as a standalone quick-reference. The checklist extracts actionable items from the guide for fast pre-flight review.

**Alternative considered**: Everything in one file. Rejected because the checklist needs to be scannable in 30 seconds — embedding it in a long guide defeats the purpose.

### 2. Structure by concern, not by workflow step
**Decision**: Organize the guide by planning concern (scope, dependencies, testing, sizing) rather than chronologically (step 1: write brief, step 2: run plan, step 3: review). Users need to jump to the relevant section, not read linearly.

**Alternative considered**: Step-by-step tutorial format. Rejected — that's already covered in `docs/orchestration.md`. The guide should be a reference, not a tutorial.

### 3. Web project patterns as a dedicated section
**Decision**: Include a "Web Project Patterns" section covering typical full-stack patterns (DB schema changes, auth layers, API routes, UI components, deployment). These are the most common orchestration targets.

**Alternative considered**: Generic patterns only. Rejected — the user explicitly requested web-project-specific guidance, and most orchestration runs target Next.js/Rails/Django-style projects.

### 4. Real examples from observed failures
**Decision**: Include anti-patterns derived from real orchestration failures (merge conflicts from parallel union-type edits, missing `depends_on`, oversized changes that stall). Anonymize project names per the openspec artifacts rule.

### 5. Language: English
**Decision**: Write the guide in English. The existing `docs/orchestration.md` is in English. The PM guide is in Hungarian but targets a different audience.

## Risks / Trade-offs

- **Risk**: Guide becomes outdated as orchestrator evolves → **Mitigation**: Focus on principles (scope isolation, dependency management) that are stable regardless of implementation changes
- **Risk**: Too long, nobody reads it → **Mitigation**: Separate checklist for quick reference; guide uses headers and bullet points for scannability
- **Trade-off**: Web-specific patterns may not apply to non-web projects → **Mitigation**: Clearly label the section; principles in other sections are universal

## Open Questions

None — the scope is documentation-only with no code changes.
