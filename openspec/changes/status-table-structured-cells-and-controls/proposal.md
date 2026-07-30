## Why

A reader looking at a project's rows asked for something the surface cannot currently give: a
source column that says *when* and *who*, instead of an opaque identifier. The request is right
and the fix is mostly not ours — but **one half of it is, and it is a precondition rather than a
follow-up.**

**Measured before proposing anything** (`StatusTable.tsx:75-79`, `:99`): `cellText` returns the
empty string for any object, and `facetColumns` skips any column whose values are not scalar. So
a project that improves its data by publishing a structured value today would find that value
**disappears from search and from every filter** — and the failure is in the reassuring direction,
because the search box answers "no rows" rather than "this column is not indexed". The producer's
improvement would make the surface worse.

**Where the boundary runs, with the evidence that decides it.** The date and the participants
cannot come from the framework. In one real answer the source values include three that embed a
date and two that do not. A framework-side parser for that shape would work on some rows and
silently fail on the rest — the exact defect class this layer exists to avoid, and the reason the
structure has to come from the side that generated it.

**And the existing controls are already thin for the columns that matter.** A column becomes
filterable today when its values are categorical, which is correct and is not enough: an "age in
days" column of 49/54/56/85 over twenty rows technically qualifies and gives a facet of one-row
chips — a control that cannot narrow anything, which the surface's own rules call worse than no
control.

## What Changes

- **A structured cell is rendered, searched and filtered.** Its leaf values contribute to free-text
  search; its sub-paths (`source.kind`, `source.date`) become filterable in their own right.
- **The control follows the SHAPE of the values, never the field's name.** Numeric columns get a
  range; date-shaped columns get a period. Categorical stays as it is.
- **Filter state becomes addressable**, so a narrowed view survives a reload and can be handed to
  someone else.
- **Columns can be hidden — and a hidden column still reports a failure**, per the surface's
  standing rule that compacting must never hide one.
- **Search can be narrowed to one column**, alongside the global box.

## Capabilities

### New Capabilities
<!-- None. Every requirement below extends how the existing surface renders and narrows rows. -->

### Modified Capabilities
- `project-status-surface`: structured cells become first-class (searchable and filterable),
  controls are selected by value shape, filter state is addressable, and hiding a column is
  subject to the existing failure-visibility rule.

## Impact

- `web/src/components/StatusTable.tsx` — indexing, facets, the new controls, column visibility.
- `web/src/components/statusShape.tsx` — value-shape classification, shared with the renderer.
- URL/query handling for the status surface.

**Deliberately NOT changed:** no field name becomes meaningful, no value is parsed for domain
content (a date-shaped *column* is detected from its values; an identifier that happens to contain
a date is not mined), and nothing is hidden that could conceal a failure.
