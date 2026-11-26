## Why

Measured 2026-11-26 21:54 (`relay.log`): a finished turn's next step (`continuation`) the
operator had not seen yet was released when the continuation hook's time ran out (3300 s),
and it left the fleet board and the channel. B-247 keeps a timed-out QUESTION on the relay
through a carrier; the continuation path had nothing to pick it up. Bug register B-250. The
owner asked the same evening that nothing drop off (*„hogy lehet legközelebb ne maradjon ki
semmi?"*), and answered this one with *„Javítsd a B-250-et: a lejárt continuation maradjon a
boardon"* (written by the auto-answer from this session's own proposal).

## What Changes

- When the continuation hook releases a next step ONLY because its time ran out, it hands a
  carrier job to the backfill (`on_timeout` → `relay_backfill.repull_continuation`).
- The carrier, for a fleet-held session only, posts the next step again (same text and
  suggestions, the board keeps its original age), waits without the hook's limit (the 24 h
  last-resort cap), and types the channel's answer into the idle session as the same
  instruction the hook would have woken it with.
- It lets go untyped when the session moved on, a prompt was typed, the fleet released it,
  the switch went off, or its terminal is gone. A next step in a plain terminal stays there,
  as before.

## Capabilities

### Modified Capabilities

- `relay-backfill`: a timed-out next step is carried on, like a timed-out question.

## Impact

`lib/set_orch/fleet/question_relay.py` (`wait_one(timeout=, note=)`),
`lib/set_orch/fleet/continuation.py` (`continue_turn(on_timeout=)`),
`lib/set_orch/fleet/relay_backfill.py` (`repull_continuation`, `run_continuation`,
`fleet_label`, `run_job` routing), `bin/set-hook-continue-relay`.
