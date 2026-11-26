## Why

Measured 2026-11-26 20:34–20:41: three questions the owner had not answered yet left the relay
when the hook's own time ran out (`question_relay.timeout_s`, bounded by the runtime's hook
limit). They stayed open in their terminals, the fleet panel's hourglass vanished, and the
owner saw "nothing waiting" while three agents waited on him (*„eltűnt a korábbi homokóra …
pedig 3 question várakozik"*). A pulled-in question's carrier copied the same 55-minute limit,
so it would have dropped a second time. Bug register B-247.

## What Changes

- When the hook releases a question ONLY because its time ran out, it parks it and pulls it
  straight back in through the backfill: a carrier, which no hook limit binds, keeps it on the
  relay (one more channel post, the decider runs again).
- A carrier waits while its question is open, its terminal lives and the switch is on; its
  only time bound is a 24-hour last-resort cap.
- `set-relay-backfill --help` prints its usage and pulls nothing in (it used to run a real
  pull-in); an unknown option exits 2.

## Capabilities

### Modified Capabilities

- `relay-backfill`: a timed-out question is re-pulled; a carrier has no relay timeout.

## Impact

`lib/set_orch/fleet/question_relay.py` (`relay(repull=…)`), `lib/set_orch/fleet/relay_backfill.py`
(`repull_after_timeout`, `CARRY_MAX_S`, `main` usage), `bin/set-hook-question-relay`.
