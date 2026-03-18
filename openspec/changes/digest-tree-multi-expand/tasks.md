# Tasks: digest-tree-multi-expand

## 1. Fix OverviewPanel

- [ ] 1.1 Change `expandedReq` state from `string | null` to `Set<string>` in OverviewPanel [REQ: multi-select-expansion]
- [ ] 1.2 Update toggle logic: add/remove from Set instead of replace [REQ: multi-select-expansion]
- [ ] 1.3 Update `isExpanded` check: `expandedReqs.has(r.id)` instead of `expandedReq === r.id` [REQ: multi-select-expansion]
- [ ] 1.4 Add Expand All / Collapse All buttons to OverviewPanel header [REQ: expand-all-and-collapse-all-controls]

## 2. Fix RequirementsPanel

- [ ] 2.1 Change `expandedReq` state from `string | null` to `Set<string>` in RequirementsPanel [REQ: multi-select-expansion]
- [ ] 2.2 Update toggle logic and `isExpanded` check [REQ: multi-select-expansion]
- [ ] 2.3 Add Expand All / Collapse All buttons to RequirementsPanel filter bar [REQ: expand-all-and-collapse-all-controls]

## 3. Build and verify

- [ ] 3.1 Build frontend and verify no TypeScript errors [REQ: multi-select-expansion]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN user opens row A then row B THEN both remain expanded [REQ: multi-select-expansion, scenario: open-multiple-rows]
- [ ] AC-2: WHEN user clicks expanded row THEN only that row collapses [REQ: multi-select-expansion, scenario: toggle-individual-row]
- [ ] AC-3: WHEN user clicks Expand All THEN all rows with AC are expanded [REQ: expand-all-and-collapse-all-controls, scenario: expand-all]
- [ ] AC-4: WHEN user clicks Collapse All THEN all rows collapse [REQ: expand-all-and-collapse-all-controls, scenario: collapse-all]
