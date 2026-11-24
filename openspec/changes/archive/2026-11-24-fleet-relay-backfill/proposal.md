## Why

The owner turned the question relay and the automatic answers on while three agents already
had a question open in their terminals, and none of the three was relayed or decided
(owner, 2026-11-24: *„volt 3 kérdésem már a rendszerben majd kértem hogy auto answer és relay
on de a regi kerdeseket mar nem automatizalta. bekapcsoáskor a regi kerdeseket is be kell
huzni"*). Measured: the relay switch went off at 13:04:41 and on at 13:42:09
(`journalctl --user -u set-web`). The hook releases a question to the terminal at once while
the switch is off, and nothing looks at it again. At 13:5x, three fleet-held sessions had an
outstanding `AskUserQuestion` with no relay waiting record. Turning the switch on reads as
"I am away now", and that is exactly when those questions are left behind.

## What Changes

- Turning the **relay switch on** pulls in every question already open in a fleet-held
  terminal. Each one is handed to the relay's outbound as an ordinary question, so it reaches
  the operator's channel, and the decider when automatic answers are on. The answer reaches
  the agent through its fleet terminal: Esc closes the open dialog, then one typed line
  carries the answers.
- Turning **automatic answers on** also pulls in (a) those terminal questions, and
  (b) questions the relay already holds that no decider has seen. Those get a decision
  without being posted to the channel a second time.
- A question open in a terminal the fleet does not hold cannot be typed into. It is counted
  and named in the switch's response and the log, and it stays in the terminal.
- A pulled-in question that gets answered in the terminal, released, or overtaken by a newer
  turn is dropped. Nothing is typed into a session that has moved on.
- `set-relay-backfill` runs the same pull-in by hand.

## Capabilities

### New Capabilities
- `relay-backfill`: what is pulled in when a switch turns on, how the answer reaches a
  question asked before the relay saw it, and when a pulled-in question is dropped.

### Modified Capabilities
- `fleet-auto-answer`: the decider can decide a question that is already posted, without
  forwarding it again and without releasing it when it cannot answer.

## Impact

- New: `lib/set_orch/fleet/relay_backfill.py` (core, fleet layer), `bin/set-relay-backfill`.
- Changed: `lib/set_orch/fleet/auto_answer_worker.py` (a no-forward mode),
  `lib/set_orch/api/fleet.py` (both toggles start the pull-in and report what it did).
- Uses the owner daemon's terminal write, through the same Esc / line / Enter sequence as the
  takeover interrupt (`takeover.owner_interrupt`).
- No UI change: pulled-in questions appear in the relay's existing waiting list.
