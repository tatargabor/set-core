## Why

A project can publish a number that is **correct and narrower than its name suggests** — a
"not-tracked" count describing the project's own register rather than the world, a "tracked"
count that is a known lower bound because one input is still hand-written. The status envelope
carries three "do not read it that way" signals and none of them fits: `gaps` is per-command,
`errorClass` is per-failure, `deprecated` is per-field-name, and all three describe something
**absent or wrong**. Here the command succeeds, the field exists, and the value is right — only
the reading is wider than the fact.

So the number lands on screen at the same visual weight as every other number and the caveat
stays in a conversation: **the number travels, the caveat does not.** That is the false-absence
class one layer up, and it is the reason a caveat has to ride on the envelope rather than on a
convention.

The shape below is not proposed here for the first time — it was negotiated with a consumer over
several rounds and settled. This change implements what was agreed; the arguments are recorded
in the design so the next reader can re-open a decision rather than merely inherit it.

## What Changes

- **A `caveats` object on the status envelope**: key → one sentence, **written by the producer,
  never decided by the framework** — exactly how `deprecated` already works.
- **A `"*"` key carries the command-level default.** It always applies and always shows.
- **Per-field keys ADD to it. They never override.** No replacement marker exists, and adding one
  later must be a separately named field rather than a change to the default's semantics.
- **The count comes from the data; the declaration only says what to look for** — inherited from
  `presentDeprecations`, or a caveat printed for a field the project stopped sending becomes the
  next false absence.
- **A declared-but-absent key is reported as diagnostics, never as a gate.** The framework cannot
  distinguish a typo from a legitimately-absent key, and a gate that fires daily on a legitimately
  zero value is dead within a week and takes the real warning with it.
- **The caveat renders beside the number, where the reader is standing** — never in a tooltip and
  never on another tab. The `"*"` renders once, in the section header.

## Capabilities

### New Capabilities
- `status-contract-caveats`: how a project declares that a correct value means something narrower
  than its name, how the framework carries that declaration without interpreting it, and where the
  caveat has to appear.

### Modified Capabilities
<!-- None. The envelope's existing fields keep their requirements unchanged; `caveats` is
     additive and an envelope without it behaves exactly as today. -->

## Impact

- `lib/set_orch/project_status.py` — `StatusResult.caveats`, its validator, and the field on the
  JSON the dashboard reads.
- `web/src/components/statusShape.tsx` — the presence check counted from the data, and the
  rendering contract.
- The dashboard components that render a command's fields — the header line and the per-value
  slot.

**Deliberately NOT changed:** no framework-side key names, no interpretation of any caveat's
text, and no gate. A project that sends no `caveats` sees no difference whatsoever.
