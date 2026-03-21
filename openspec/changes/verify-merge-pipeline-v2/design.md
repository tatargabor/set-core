# Design: verify-merge-pipeline-v2

## 1. E2E Gate — Baseline Comparison

### Problem
The E2E gate runs ALL Playwright tests. Pre-existing failures in unrelated tests cause valid changes to fail.

### Solution: Baseline Filtering

```
  ┌─────────────────────────────────────────┐
  │  E2E Gate (in worktree, post-integration)│
  │                                          │
  │  1. Run Playwright → collect failures    │
  │  2. If all pass → PASS                   │
  │  3. If failures:                         │
  │     a. Check main baseline cache         │
  │     b. new_failures = wt_fails - main    │
  │     c. If no new failures → PASS         │
  │     d. If new failures → FAIL            │
  │        (only report NEW failures)        │
  └──────────────────────────────────────────┘
```

**Main baseline cache**: Run Playwright on main once per orchestration run, cache results in `wt/orchestration/e2e-baseline.json`. Invalidate when main HEAD changes (after a merge).

```json
{
  "main_sha": "abc123",
  "timestamp": "2026-03-21T12:00:00Z",
  "failures": ["e2e/equipment-catalog.spec.ts:33", "e2e/header-nav.spec.ts:12"],
  "total": 75,
  "passed": 62
}
```

**Cost**: One extra E2E run per orchestration cycle (amortized across all changes). Much cheaper than false-fail retries.

**Known limitation**: When change A merges and breaks test X on main, the regenerated baseline absorbs that failure. Change B's gate then treats test X as pre-existing and ignores it. This is acceptable — if A's code broke X, A should have been caught by its own E2E gate. If it wasn't (because X wasn't affected pre-merge), this is a genuine integration issue that the phase-end E2E would catch. Log a warning when baseline regenerates so operators can investigate.

### Alternative Considered: Scope-based test filtering
Run only tests matching changed files (e.g., `src/app/kavek/` → `e2e/product-detail.spec.ts`). Rejected because:
- Mapping is fragile (indirect dependencies)
- Misses integration regressions
- Requires project-specific configuration

## 2. E2E Server — Playwright webServer Only

### Current (broken)
```python
if not managed_server:
    e2e_port = E2E_PORT_BASE + random.randint(0, 99)  # nobody listens here
    health_check(port)  # always fails → skip
```

### New
```python
if not pw_config["has_web_server"]:
    return GateResult("e2e", "skipped",
        output="playwright.config has no webServer — "
               "add webServer config or set e2e_command='' to disable")
```

Remove `E2E_PORT_BASE`, `health_check` call, manual `PW_PORT` env, and `pkill` cleanup. Playwright's webServer handles everything: starts dev server, waits for ready, allocates port, cleans up.

## 3. Post-Merge Simplification

### Current post-merge steps
```
ff-only merge → tag → coverage → deps_install → custom_cmd →
plugin_directives → i18n_sidecar → scope_verify → smoke_pipeline →
hook → cleanup → sync_worktrees
```

### New post-merge steps
```
ff-only merge → tag → coverage → deps_install → custom_cmd →
plugin_directives → i18n_sidecar → hook → cleanup → sync_worktrees
```

**Removed:**
- `scope_verify` — already done in verify gate on the same code
- `smoke_pipeline` — ff-only produces identical code to what passed verify gate

**Rationale**: After integration merge (main→worktree) + full verify gate pass, the worktree contains exactly `main + change`. An ff-only merge moves main's HEAD to that exact commit. The code on main is bitwise identical — retesting is waste.

**Exception preserved**: `deps_install` stays because lockfile resolution may differ. `custom_cmd` and `plugin_directives` stay because they may have side effects (migrations, cache warmup).

## 4. Decomposer Grouping

### Problem
The decomposer treats each requirement/bug as a separate change. 7 bugs → 15 changes (some split further by requirement).

### Solution: Prompt-level grouping heuristic

Add to decompose prompt:
```
GROUPING RULES:
- Group bugfixes that touch the same directory/domain into ONE change
- Group S-complexity changes into larger M-complexity bundles
- Target: max_parallel × 2 changes (e.g., 3 agents → 6 changes max)
- Each change should be 30-90 min of agent work, not 5 min micro-fixes
- Name grouped changes by domain, not individual bug:
  "frontend-page-fixes" not "fix-product-detail-500"
```

### Where
`lib/set_orch/templates.py` — `_PLANNING_RULES_CORE` string, in the output constraints section. Also inject `max_parallel` value into the prompt context so the LLM can optimize change count.
