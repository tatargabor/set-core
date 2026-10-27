## Why

A consumer's release board needs its process to keep its shape. The obvious implementation —
collect the stages present in the answer into a set — silently drops any stage that happens to be
empty, so a board reports a stage of the project's process as non-existent whenever nothing is
sitting in it, and two readers filtering differently see different columns without either knowing
why.

Four conditions were agreed with the producer on 2026-08-29 and accepted the same day, one of them
promoted to a mandatory requirement in **their** spec. In exchange for keeping their `unknown`
bucket *outside* the declared order, this framework undertook to render any value absent from the
order **visibly and distinctly**, never dropped and never silently sorted last.

**That undertaking is not implemented, and the gap has already shaped somebody else's design.**
Measured 2026-08-29: `stageOrder` appears in exactly one file in this repository, a document — no
code, no test, no spec. What ships does the opposite: an unrecognised role is discarded
(`lib/set_orch/project_status.py:679`, comment *"Inert by design"*; `web/src/components/statusShape.tsx:857-865`,
returning `null`). On the strength of the promise the producer rewrote their model — `unknown`
became *the absence of a signal* rather than a terminal station, and they explicitly declined to
invent a private sentinel. Their own adversarial review then found lane keys that match no declared
stage and scored the consequence as "they land in set-core's marked bucket". Today the true
consequence is that every one of those cards silently disappears. An unbuilt promise inverted the
fail direction of another team's review finding. Tracked as **B-124**.

## What Changes

- The role vocabulary grows from six entries to seven: the paired form `{"stageOrder": [...]}` joins
  `{"progressOf": …}` and `{"limitOf": …}`, the only novelty being that its argument is an array of
  strings rather than a field name. **The producer-facing envelope shape is already agreed** and is
  not reopened here.
- A declared stage order is honoured as a **static declaration of the project's process**: it is
  read from the declaration and never computed from the values present in the answer.
- A stage declared in the order but holding no items is **rendered**, not dropped.
- A value **absent** from a declared order is rendered **visibly and distinctly** — present, marked,
  and never sorted silently to the end. This is the promised half and the one with the dangerous
  fail direction.
- The vocabulary stays **closed** afterwards. No `stageColors`, `stageIcons`, `stageLabels`. The
  *order* is data because the process belongs to the project; everything visual stays here. Stated
  as an explicit non-goal because the next request is otherwise about colours, and that one breaks
  the lock.

**No board, and no columns.** Three guarantees only: the order is not lost, an unmatched value stays
visible, and an empty declared stage is shown. Whether that renders as columns, a grouped list, or
one ordered table column stays the framework's call.

## Capabilities

### New Capabilities

None. This extends two existing capabilities rather than introducing one — the declaration travels
through the machinery `project-status-field-roles` already defines, and it is drawn by the surface
`project-status-surface` already governs.

### Modified Capabilities

- `project-status-field-roles`: the closed vocabulary gains a seventh entry, so the requirement that
  enumerates it changes; and a new requirement fixes the *static* reading of the order — declared,
  never derived from the data — because that is the only property that makes an empty stage
  survivable.
- `project-status-surface`: a new requirement governing how a declared order affects presentation —
  an empty declared stage is drawn, and a value outside the order is drawn visibly and marked rather
  than dropped or sorted last.

## Impact

- **Layer 1, Python** — `lib/set_orch/project_status.py`: the `display` parser currently falls
  through on any one-key object whose form is not in `PAIRED_ROLES`, discarding `stageOrder`
  entirely. The parser gains the array-argument form, with validation of the array's shape.
- **Renderer** — `web/src/components/statusShape.tsx`: the role resolver returns `null` for any form
  it does not recognise, so the declaration never reaches the table.
- **Renderer** — `web/src/components/StatusTable.tsx`: the row-ordering pipeline is where a stage
  order takes effect. `StatusTable` reads no declaration today; roles reach it only through the
  `renderValue` closure, so this is the first declaration the table itself consumes. That is the
  substantive structural change in this work.
- **Contract, not code** — the producer-facing shape is `"display": { "<field>": { "stageOrder":
  [...] } }`. The `{cards: …}` form the producer first proposed is *not* adopted: it names a view,
  which is the appearance leak the vocabulary lock exists to prevent, and it was measured to be
  dropped silently by both sides.
- **Nothing is blocked downstream.** The consumer's answer is a plain array today and renders as a
  table; this change only improves it. The producer has been told explicitly to keep building
  against the flat array and not to wait for this.
- **Out of scope:** writing. Moving a card stays the producer's, through the existing `actions`
  pattern.
