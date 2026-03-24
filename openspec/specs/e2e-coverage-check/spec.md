# Spec: E2E Coverage Check

## Requirements

### REQ-1: Decompose injects e2e requirements into scope
The web profile `decompose_hints()` MUST include a hint that tells the planner to add explicit e2e test requirements per change. For CRUD features, the scope must list: create (form fill + submit + verify), read (list + detail), update (edit + verify), delete (confirm + verify).

### REQ-2: E2e coverage gate scans diff for assertion patterns
A new `e2e_coverage` gate in the verifier MUST:
- Extract scope keywords (CRUD, form, auth, admin, etc.)
- Scan `*.spec.ts` files in the change diff
- Check for matching assertion patterns (e.g., `getByRole('button')`, `fill(`, `click(`, `toHaveURL`, `toContainText`)
- Produce a coverage report: which operations are tested vs missing

### REQ-3: Coverage gaps injected into review prompt
When the `e2e_coverage` gate finds gaps, the review prompt MUST include a highlighted section:
```
⚠ E2E COVERAGE GAPS:
- create: NOT TESTED (no form submit assertion found)
- delete: NOT TESTED (no delete/confirm interaction found)
FIX REQUIRED: Add e2e tests for missing operations.
```
The reviewer treats this as a CRITICAL finding.

### REQ-4: Gate is non-blocking with review escalation
The `e2e_coverage` gate itself is WARN (not blocking) — false positives from assertion scanning are possible. But the review gate receives the coverage report and decides whether to FAIL.

### REQ-5: Layout consistency rule in web template
Add a rule to the web template: "All pages within a route group must use the shared layout. Admin e2e tests must verify sidebar/nav is visible on every admin page."

## Acceptance Criteria

- [ ] Web profile `decompose_hints()` includes CRUD e2e test requirements
- [ ] `_execute_e2e_coverage_gate()` scans diff for assertion patterns
- [ ] Coverage report injected into review prompt when gaps found
- [ ] Gate produces WARN (not FAIL) — review gate decides
- [ ] Web template rules include layout consistency requirement
- [ ] planning_rules.txt includes explicit CRUD test checklist
