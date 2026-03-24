# Design: E2E Coverage Enforcement

## Approach

Three layers working together — each catches what the previous missed:

```
LAYER 1: DECOMPOSE (planning time)
  decompose_hints() → planner puts e2e requirements in scope
  "This change MUST include e2e tests for: create, read, update, delete"

LAYER 2: GATE (verify time)
  _execute_e2e_coverage_gate() → scans diff for assertions
  Produces coverage report: {create: false, read: true, ...}

LAYER 3: REVIEW (verify time)
  Review prompt includes coverage gaps
  Reviewer fails if critical operations untested
```

## Key Decisions

### D1: Scope keyword extraction is heuristic
Extract operation types from scope text using simple keyword matching:
- CRUD keywords: "create", "add", "new", "edit", "update", "delete", "remove"
- Form keywords: "form", "submit", "input", "validation"
- Auth keywords: "login", "register", "protect", "auth"
- Navigation keywords: "navigate", "redirect", "route", "layout"

Not perfect but catches 90% of cases. The review gate handles false negatives.

### D2: Assertion pattern scanning
Scan `*.spec.ts` files for Playwright assertion patterns:
- Form interaction: `fill(`, `selectOption(`, `check(`
- Button click: `click(`, `getByRole('button'`
- Navigation: `toHaveURL(`, `goto(`
- Content verification: `toContainText(`, `toBeVisible(`
- Delete confirmation: `getByRole('dialog'`, `confirm`

Map these to operation types and compare against scope requirements.

### D3: Coverage report format
```json
{
  "scope_requires": ["create", "read", "update", "delete"],
  "tested": ["read"],
  "missing": ["create", "update", "delete"],
  "test_files": ["tests/e2e/admin-products.spec.ts"],
  "assertion_count": 3
}
```

### D4: Review injection point
The coverage report goes into `build_design_review_section()` output alongside design compliance. The reviewer sees it as a structured finding, not buried in prose.

## Files to Modify

| File | Change |
|------|--------|
| `modules/web/set_project_web/project_type.py` | `decompose_hints()` — add CRUD e2e checklist hint |
| `modules/web/set_project_web/planning_rules.txt` | Add CRUD test checklist section |
| `lib/set_orch/verifier.py` | New `_execute_e2e_coverage_gate()` |
| `lib/set_orch/templates.py` | Inject coverage report into review prompt |
| `modules/web/set_project_web/templates/spa/rules/components.md` | Add layout consistency rule |
| `modules/web/set_project_web/templates/nextjs/rules/components.md` | Same |
