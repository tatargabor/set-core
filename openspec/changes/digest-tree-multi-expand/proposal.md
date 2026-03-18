# Proposal: digest-tree-multi-expand

## Why

The Digest/Overview and Requirements tabs in wt-web use a single-selection expansion pattern (`string | null` state) that only allows one requirement row to be expanded at a time. Opening one row automatically collapses the previously open row, making it impossible to compare acceptance criteria across requirements. There are also no Expand All / Collapse All controls.

## What Changes

- **Fix**: Change expansion state from `string | null` to `Set<string>` in `OverviewPanel` and `RequirementsPanel` so multiple rows can be open simultaneously
- **New**: Add Expand All / Collapse All buttons to both panels

## Capabilities

### New Capabilities
- `digest-multi-expand` — multi-select expansion and bulk expand/collapse controls for digest tree views

### Modified Capabilities
_(none)_

## Impact

- `web/src/components/DigestView.tsx` — `OverviewPanel` and `RequirementsPanel` state management and UI
