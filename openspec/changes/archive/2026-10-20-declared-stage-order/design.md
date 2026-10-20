## Context

The producer declares its process; the framework draws it. The declaration travels in the existing
`display` block, and the four conditions behind it were agreed and accepted on 2026-08-29 (recorded
in `docs/integration/consumer-integration.md`). This change implements the framework's half.

Current state, measured rather than recalled:

- `lib/set_orch/project_status.py:669-681` parses `display` into roles. A one-key object is accepted
  only when its form is in `PAIRED_ROLES` **and** its argument is a non-empty string. `stageOrder`
  matches neither test and falls through the loop with the comment *"Inert by design."*
- `web/src/components/statusShape.tsx:855-870` resolves a declared role for rendering and returns
  `null` for any form it does not recognise.
- `web/src/components/StatusTable.tsx:739-768` is the single row-ordering pipeline. **`StatusTable`
  reads no declaration at all today** — roles reach the tree only through the `renderValue` closure
  in `StatusValue.tsx:524-529`. A stage role is therefore the first declaration the table itself
  must consume, and that is the structural change in this work.

Both drop paths fail the same way: silently, in the reassuring direction. That is what B-124 records,
and it is why a test here has to prove the value *arrives*, not merely that nothing threw.

## Goals / Non-Goals

**Goals** — exactly the three guarantees that were promised:

1. The declared order is not lost, and is read statically from the declaration.
2. A declared stage holding nothing is drawn.
3. A value outside the declared order stays visible and is marked.

**Non-Goals**, stated because each has an obvious next request attached:

- **No board and no columns.** The requirement is satisfied by an ordered, grouped table. Whether a
  board is ever built is a separate decision with a separate cost.
- **No appearance in the contract.** No `stageColors`, `stageIcons`, `stageLabels`, widths or
  positions. The vocabulary closes again at seven immediately after this change.
- **No writing.** Moving a card stays the producer's, through the existing `actions` pattern.
- **No inference.** A stage order is never guessed from a field name, and never derived from values.

## Decisions

### D1 — `stageOrder` is a paired role with an array argument, not a new top-level key

Adopted shape: `"display": { "<field>": { "stageOrder": ["planned", …] } }`.

*Alternative rejected:* the producer's first proposal, `"display": {"cards": {"<field>": {...}}}`.
The `cards` layer names a **view**, which is the appearance leak the vocabulary lock exists to
prevent. It was also measured to fail silently: no `cards` key is parsed anywhere in `web/` or
`lib/set_orch/`, so the whole block would be dropped by both sides without a word.

*Consequence:* `PAIRED_ROLES` currently assumes a string argument. Rather than loosen that test for
every form — which would let a malformed `progressOf` through — the array form is validated
separately and explicitly.

### D2 — a malformed order yields NO role, never a partial one

An argument that is not an array, is empty, or holds a non-string or empty string leaves the field
entirely unroled.

*Why not salvage the valid entries:* a partial order is the worst outcome available. It renders as a
complete process that is quietly missing stages — the false-value shape — and the producer gets no
signal. Inert matches how every other malformed declaration already behaves, and the value still
renders exactly as it does today.

### D3 — an undeclared value renders in a distinct, explicitly marked trailing group

Undeclared values are grouped together after the declared stages, and that group carries a structural
marker naming it as outside the declared process.

*Why trailing is acceptable:* the requirement forbids being sorted **silently** to the end. Position
is not the defect — the absence of a mark is. Placing them first would be equally arbitrary and would
push the project's real process below unrecognised data.

*Why the marker is structural, not styling:* a colour or an icon would be a rendering choice a future
theme could drop. The group is marked in the DOM as a distinct region with its own label, so the
distinction survives restyling. This also keeps the mark on the reader's side of the screen rather
than only where the value lives — the same rule `ui-quality.md` states for hidden failures.

*Explicitly not an error state:* an unmatched value is legitimate producer data and may be the first
sight of a stage the declaration has not caught up with. It is marked as *outside the declared
process*, never as broken. Red stays reserved for broken.

### D4 — an empty declared stage is carried by a group header, which is what makes it drawable

A table has no row for a stage with no items, so the guarantee needs a carrier. The table renders
stage-grouped sections with headers; a declared stage with no rows still gets its header, showing a
count of zero.

*This is the whole reason the order must be static (D5).* "Done: 0" is a real statement about a
release; dropping it destroys exactly the information the producer asked to preserve.

### D5 — the order is resolved from the declaration alone, before any row is examined

Resolution takes the declared array and produces the group list. Rows are then distributed into those
groups. The order is never appended to, reordered, or filtered by what the rows contain.

*Alternative rejected:* collecting present stages into a `Set` and ordering that. It is the more
natural implementation and it is the bug — measured precedent on this very contract, where a
producer's `display` block shrank from eleven entries to five because it was computed from what
happened to be present.

### D6 — group counts are computed from the full answer, never from the rendered slice

`ROW_CAP = 25` (`StatusTable.tsx:66`) can hide rows. Stage counts and emptiness are therefore derived
from the complete row set before the cap applies.

*Why this is called out:* counting the rendered slice would make a stage with 30 hidden rows report
as holding fewer, and a stage whose every row fell past the cap report as **empty** — turning the
honest cap into a false-absence. That is measuring the proxy instead of the thing, and it would land
precisely on the guarantee this change exists to provide.

## Risks / Trade-offs

- **`StatusTable` gaining a dependency on the role declaration** → It is the first one, so the seam
  is new. Mitigated by reading roles through the existing `useRoles()` hook rather than threading a
  new prop, and by keeping the no-declaration path byte-identical to today's ordering (asserted by a
  scenario).
- **Grouping changes the table's shape for every consumer** → Mitigated by grouping *only* when a
  stage role is declared for a field. No declaration, no grouping, no visual change anywhere.
- **The cap and the groups interact** → Covered by D6, and worth a test that puts more than `ROW_CAP`
  rows in one stage and asserts the header count is the true one.
- **A test that passes with and without the fix** → The two defects here are silent drops, so a test
  asserting "nothing threw" would pass on unfixed code. Every test in this change asserts the value
  *arrives*: the role is present, the empty stage is present, the undeclared value is present **and**
  marked. Proved by stash-and-rerun per `.claude/rules/evidence-discipline.md`.

## Migration Plan

No migration. The declaration is optional and absent everywhere today, so the change is inert until a
producer declares a `stageOrder`. Rollback is reverting the commit; no data shape, stored artifact or
API response changes for a producer that declares nothing.

The consumer has been told explicitly to keep building against their flat array and not to wait for
this, so nothing downstream is sequenced behind it.

## Open Questions

- **Where the group marker's label text lives.** The framework decides labels (F4), so it is a
  renderer string; it is not settled whether it reads as "outside the declared process" or shorter.
  Does not block implementation — the structure carries the guarantee, the wording is adjustable.
- **Whether a declared stage order on a nested field should group a nested table.** The agreed use is
  a top-level list. Deliberately deferred: not promised, not requested, and adding it speculatively
  would widen the first declaration `StatusTable` ever reads.
