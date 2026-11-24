## Why

B-215 part 2: an agent that asked another project through the fleet and ended its turn is
not woken when the reply arrives. It sits idle, the reply looks delivered, and nothing moves
until a person notices. Measured 2026-11-24: a session's REQUEST at 08:00:29 was answered at
08:08:24 with a linked ANSWER, and the session stayed idle until the owner typed at 08:09.
The owner asked for it to be built (2026-11-24) under his constraints: wake a session only for
its own business, a reply linked to its own request, never for room traffic in general,
because every needless wake re-reads a whole context.

## What Changes

- When an engagement (a request sent through the fleet) is answered, the fleet wakes the
  asking agent ONCE: it types one line into the asker's fleet terminal naming the room and
  the request, so the agent reads the reply and continues.
- Only when the asker is a fleet-held terminal, its turn has ended (the prompt is free), and
  it has not moved since the reply arrived. Also not while the operator typed into it in the
  last two minutes, and not while automatic answers are off for that terminal.
- Each answered engagement records whether and why it was or was not woken, so a reply wakes
  at most once and the reason stays readable.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `engagement-takeover`: a requirement for waking the asker on a linked reply.

## Impact

- `lib/set_orch/fleet/engagement.py` (two fields), `lib/set_orch/fleet/takeover.py` (the wake
  decision and a typing helper without Esc), `lib/set_orch/api/fleet_mandate.py` (the round
  also wakes askers).
