# Proposal: Resume Context Restoration

## Problem

When an agent change is **resumed** after a failure (merge conflict, integration e2e fail, review gate fail), the design context, project conventions, and Figma source code from the original `input.md` get **lost**, causing the agent to drift away from the original design specs.

### Observed in minishop-run1

- `admin-products` initial dispatch: input.md contained **480+ lines** with full Figma source code (`AdminSidebar.tsx` with `bg-gray-900 text-white`, `AdminProducts.tsx`, etc.)
- 3 retry cycles followed (1× merge conflict, 2× review fail)
- **Each retry replaced `task_desc` with the retry_context only** (224 → 3780 → 6937 chars of fix instructions)
- Final result: agent built admin layout with `bg-gray-50` (light) instead of `bg-gray-900` (dark) — completely missed the Figma design

### Root cause

`resume_change()` in `dispatcher.py` (L2374):
```python
if retry_ctx:
    task_desc = retry_ctx  # ← only fix instructions, no design context
```

The agent runs `claude --resume` which continues the previous session. Two failure modes:
1. **Context compaction**: long sessions get compactified by Claude, dropping the Figma source code blocks
2. **Focus loss**: even uncompacted, the agent's attention is on the fix instructions, not the original design tokens

Other context that may degrade between resumes:
- Per-change `design.md` (path mentioned in initial input.md, agent forgets)
- Skeleton spec file (agent might try to recreate)
- Convention rules (`micro-web-conventions.md`, `minishop-conventions.md`)
- E2E test plan / Required Tests section
- Project knowledge (`project-knowledge.yaml`)

## Solution

Prepend a **Context Restoration Preamble** to the `retry_ctx` in `resume_change()` that re-anchors the agent to the original artifacts.

### Preamble structure

```
## Context Restoration

Before fixing the issue below, RE-READ these files to refresh your context:

1. `openspec/changes/<name>/input.md` — original task scope, requirements, design context
2. `openspec/changes/<name>/design.md` — design tokens and Figma source code (if exists)
3. `tests/e2e/<name>.spec.ts` — test skeleton (fill bodies, do NOT recreate structure)
4. `.claude/rules/*.md` — project conventions (UI library, styling rules)

Key reminders:
- Use the EXACT design tokens from design.md — do NOT fall back to shadcn defaults
- Use the components specified in the Figma source code (e.g., `bg-gray-900` for admin sidebar)
- Keep the test skeleton structure intact

## Fix Required

<original retry_ctx here>
```

### Why this works

- The agent receives a clear directive to RE-READ specific files at the start
- Even if the conversation history compacted, the file system has the truth
- The reminder is short (~300 chars) so it doesn't bloat the prompt
- Works for all retry types: merge, review fix, integration e2e fix

## What this does NOT change

- Initial dispatch flow (works correctly)
- The `retry_context` content itself (still passed)
- The set-loop CLI behavior
- The verifier pipeline
- Token tracking, model routing, etc.

## Risk

- Low: only adds a preamble string to existing flow
- Worst case: agent re-reads files unnecessarily (small token cost)
