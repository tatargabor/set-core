# Proposal: E2E Test Scaffolding

## Problem

E2E test generation relies on LLM agents to write the correct number of tests with proper REQ-ID annotations. Across 4 E2E runs (run22-run29), agents consistently under-deliver:

- **run22**: 62/494 tests (13%) — agents got narrative descriptions, not test counts
- **run23**: 222/407 tests (55%) — agents got Required Tests but followed tasks.md instead
- **run23 gate-verified**: 53/222 (24%) — most tests never ran through merge gates

The root cause: test **structure** (how many tests, what REQ-IDs, smoke vs functional) is decided by the LLM, which is unreliable. The test **content** (what to click, what to assert) is where LLM excels.

## Solution

Move test structure from LLM to Python. The dispatcher generates a **test skeleton** — a complete `.spec.ts` file with all test blocks, REQ-IDs, and `@smoke` tags pre-filled from test-plan.json. The agent's job reduces from "write tests" to "fill in test bodies".

```
BEFORE: Agent writes everything (structure + content)
  test-plan.json → [LLM reads maybe] → agent writes 25 tests (needed 131)

AFTER: Python writes structure, agent writes content
  test-plan.json → [Python: scaffold] → skeleton with 131 test blocks
                 → [LLM: agent]      → fills 131 test bodies
                 → [Python: gate]    → verifies 0 TODO blocks remain
```

## Scope

**Core** (`lib/set_orch/`):
- `test_scaffold.py` — new module: reads TestPlan, groups by REQ, generates skeleton via profile template
- `dispatcher.py` — calls scaffold after worktree bootstrap, rewrites E2E tasks to "fill skeleton"
- `merger.py` — optional TODO-count gate check

**Web module** (`modules/web/`):
- `templates/nextjs/e2e-skeleton.py` or inline — Playwright-specific skeleton format
- `project_type.py` — `generate_test_skeleton()` method on WebProjectType

**Model routing**: Skeleton generation is Python (0 tokens). Agents filling test bodies can use **sonnet** instead of opus — test body implementation is straightforward pattern-matching (page.goto, click, expect), not complex architecture. This saves ~60% on the most token-heavy phase.

## Non-goals

- Not changing how test-plan.json is generated (that works well)
- Not changing the coverage gate logic (already fixed in e2e-coverage-pipeline-fix)
- Not generating unit test scaffolds (only E2E)
