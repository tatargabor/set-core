## Why

The recorded list shipped as a disclosure inside the project header row, and the user reported
it the same day with the screen in front of them: *"funkcióban jó de szerintem ez egy popup
screen kellene legyen nagyban és nincs close most pl hogy bezárjam"*.

Both halves are one defect. A header row is as wide as a header row, so a 47-entry record with a
transcript excerpt inside it read through a letterbox. And the only way out was pressing the line
that opened it — a toggle wearing the clothes of a heading, with nothing on it saying *press me
again*. A surface that can be opened and not obviously closed is a trap, and it was reported as
one within minutes of shipping.

Documented after the fact, as the process here prescribes for behaviour that shipped without a
spec: the code shipped in `d0ecaec3` and every task below was already done when this was written.

## What Changes

- The recorded list opens as a **dialog** — large, over the page — rather than inside the header
  row it is triggered from.
- It offers the three ways out a covering layer owes the reader: an explicit close control,
  **Escape**, and a click on the backdrop. A click inside it does not close it.
- The act (restore the ticked entries) stays with the list, in the dialog's footer.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `agent-fleet-restore`: the surface requirement gains how the recorded list is presented and
  that it must be closable.

## Impact

- `web/src/components/FleetRestore.tsx` only. No route, no stored shape, no migration.
