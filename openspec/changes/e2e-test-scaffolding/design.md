# Design: E2E Test Scaffolding

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Scaffold Generation Flow                      │
│                                                                    │
│  test-plan.json ──► TestPlan (existing dataclass)                 │
│       │                                                            │
│       ▼                                                            │
│  ┌─────────────────────┐     ┌──────────────────────────┐        │
│  │ test_scaffold.py    │     │ WebProjectType           │        │
│  │ (Core — Layer 1)    │────►│ (Web Module — Layer 2)   │        │
│  │                     │     │                          │        │
│  │ group_by_change()   │     │ render_test_skeleton()   │        │
│  │ build_skeleton()    │     │ - Playwright imports     │        │
│  │                     │     │ - page/request fixtures   │        │
│  └─────────┬───────────┘     │ - test()/describe() syntax│       │
│            │                  └──────────────────────────┘        │
│            ▼                                                      │
│  tests/e2e/<change>.spec.ts  (written to worktree)               │
│  ┌────────────────────────────────────────────────────┐          │
│  │ // AUTO-GENERATED — fill test bodies, don't delete │          │
│  │ test.describe('REQ-CART-001: Add to cart', () => { │          │
│  │   test('add product → cart item created', () => {  │          │
│  │     // TODO: implement                             │          │
│  │   });                                              │          │
│  │   test('qty > stock → error', () => {              │          │
│  │     // TODO: implement                             │          │
│  │   });                                              │          │
│  │ });                                                │          │
│  └────────────────────────────────────────────────────┘          │
│                                                                    │
│  Dispatcher                                                        │
│  ├─ Calls scaffold after bootstrap                                │
│  ├─ Rewrites E2E task: "Fill test bodies in <file>"              │
│  └─ Removes narrative E2E from tasks.md (Python string ops)      │
│                                                                    │
│  Merger (optional)                                                 │
│  └─ Pre-gate: count remaining TODO blocks → warn if > 0          │
└──────────────────────────────────────────────────────────────────┘
```

## Core / Web Separation

**Core (`lib/set_orch/test_scaffold.py`)** — framework-agnostic:
- Reads `TestPlan` and `change.requirements` to filter entries
- Groups entries by REQ-ID
- Calls `profile.render_test_skeleton(entries, change_name)` → gets file content
- Writes the file to `tests/e2e/<change-name>.spec.ts` in the worktree
- Returns the path and test count for logging

**Web Module (`modules/web/.../project_type.py`)** — Playwright-specific:
- New method `render_test_skeleton(entries: list[TestPlanEntry], change_name: str) -> str`
- Generates Playwright `test()` / `test.describe()` blocks
- Knows about `page`, `request` fixtures
- Applies `@smoke` tag to smoke-type entries
- Includes `global-setup.ts` import if needed

**Other modules** can override `render_test_skeleton()` for Jest/Vitest/etc.

## Dispatcher Integration

After worktree bootstrap (existing `_dispatch_change` flow):

```python
# In dispatcher.py, after writing input.md
if test_plan_entries and profile and hasattr(profile, 'render_test_skeleton'):
    from .test_scaffold import generate_skeleton
    skeleton_path, test_count = generate_skeleton(
        test_plan_entries=test_plan_entries,
        change_name=change_name,
        worktree_path=wt_path,
        profile=profile,
    )
    logger.info("Generated test skeleton: %s (%d test blocks)", skeleton_path, test_count)
```

## Task Rewriting

The dispatcher post-processes `tasks.md` after scaffold generation:
- Finds E2E task lines (matching `tests/e2e/` or `spec.ts` or `E2E`)
- Replaces with: `"Fill test bodies in tests/e2e/<name>.spec.ts — <N> test blocks, all marked // TODO"`
- This is a Python string replacement, not LLM — deterministic

## Model Routing for E2E Changes

The test body filling task is **simpler** than feature implementation:
- Pattern: `page.goto('/path')` → `page.click('selector')` → `expect(locator).toBeVisible()`
- No architecture decisions, no API design, no state management
- Sonnet handles this well at ~60% cost savings vs Opus

The dispatcher can set `model_override: "sonnet"` for changes where:
- `change_type == "feature"` AND
- All remaining tasks are "fill test bodies" (post-scaffold)

This is a **per-dispatch** decision, not global model routing.

## TODO Gate (Optional Enhancement)

In `merger.py`, before running E2E tests:
```python
# Count remaining TODO blocks in test files
todo_count = _count_todos_in_spec(wt_path, change_name)
if todo_count > 0:
    logger.warning("E2E spec has %d unfilled TODO blocks — agent didn't complete all tests", todo_count)
```

This is a WARNING, not a blocker — some TODOs may be intentionally left for non-testable scenarios.
