# Design: digest-tree-multi-expand

## Context

`OverviewPanel` and `RequirementsPanel` in `DigestView.tsx` use `useState<string | null>` for expansion state, allowing only one row open at a time. `DependencyTree` in `ProgressView.tsx` already uses `useState<Set<string>>` correctly.

## Decisions

### D1: Adopt the same Set<string> pattern already used in DependencyTree

Change `expandedReq` from `string | null` to `Set<string>` with a toggle function identical to the one in `ProgressView.tsx`.

### D2: Expand/Collapse buttons in the table header area

Add two small buttons next to the existing column headers or filter controls. Use the `\u25BE` (expand) and `\u25B8` (collapse) glyphs consistent with existing row indicators.
