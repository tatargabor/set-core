## Why

The recorded roster only ever grew. The DELETE route
(`/api/fleet/roster/{project}/{key}`) and the `set-fleet-roster forget` CLI
have existed since the roster shipped, but neither ever reached the dashboard —
reported by the user 2026-09-17: the restore session list cannot delete, so it
grows forever. The route itself also shipped without a capability spec; this
change documents the whole forget capability retroactively and adds its surface.

## What Changes

- The restore dialog's recorded-entry row gains a trash control after the
  "what was this?" peek toggle. Armed like every act on the screen: the first
  click opens the question, the question names the entry, the confirm deletes.
- The dialog footer gains **Delete all selected** at the bottom right, over the
  ticked entries. Armed the same way, stating the count; drawn only when the
  selection is non-empty.
- Copy states the true blast radius on every control: a forget removes the
  RECORD entry only — the conversation file on disk stays, and nothing running
  is stopped.
- After any successful forget the record is re-read (per project, and the
  empty-screen panel's project list), so the screen never goes on listing
  entries the record no longer holds.
- A failed forget is shown next to where the act was offered, collected across
  a bulk delete — a delete of nine of which two failed reads as neither nine
  nor seven.

## Capabilities

### New Capabilities

- `fleet-roster-forget`: removing recorded entries from a project's roster —
  the DELETE route's contract, and the dashboard surface that reaches it.

### Modified Capabilities

## Impact

- `web/src/components/FleetRestore.tsx` — the per-entry trash control, the
  bulk delete control, the re-read wiring, the `forgetOne` act.
- `web/tests/unit/fleetRestoreSurface.test.tsx` — 7 new tests (armed per-entry
  forget, confirmed DELETE + re-read, cancel, visible failure, bulk control
  absent with no selection, bottom-right placement + arming, one DELETE per
  ticked entry, partial-failure reporting).
- No framework (`lib/set_orch/`) change: the DELETE route already existed and
  is untouched.
- `web/dist` rebuilt; visually verified against the live dashboard on port
  7400 with real roster data — armed states only, every confirm cancelled, the
  record re-read untouched afterwards.
