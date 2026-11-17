## Why

The question relay's switch reports `ready` from this machine's configuration alone. It
cannot see that a registered project's own `.claude/settings.json` never wired the relay
hooks, so a question asked in that project is shown only in its terminal while the header
says the relay is on and the owner is away, trusting the phone.

Measured 2026-11-17: `GET /api/fleet/question-relay` returned `ready: true`; one session's
AskUserQuestion appeared as a local picker with no `handed over` line in `relay.log`; its
project keeps a hand-authored hook chain that `set-deploy-hooks` never merged into. A scan of
every registered project found 47 wiring both hooks and 1 wiring neither. Bug register entry
B-182. Fail direction: silent, in the reassuring direction.

## What Changes

- `question_relay.unwired_projects()` lists the registered, non-archived projects whose
  settings (project, local, or user level) lack the AskUserQuestion relay hook, the
  wait-detect Stop hook, or both — naming which.
- The relay payload (`GET /api/fleet/question-relay`) carries that list as `unwired`.
  `ready` keeps its meaning (this machine's configuration is complete).
- The fleet header marks the count on the closed header while the relay is on, says so in
  the switch's title, and lists the projects in the relay detail.

Not in scope: wiring the hooks into a project. That project's settings are its owner's; the
screen names the gap, the owner decides.

## Capabilities

### Modified Capabilities

- `agent-question-relay`: the header now also reports projects the relay cannot reach.

## Impact

- `lib/set_orch/fleet/question_relay.py`, `lib/set_orch/api/fleet.py` (core, domain-free:
  reads settings files and the project registry only)
- `web/src/lib/fleetRelay.ts`, `web/src/components/FleetRelay.tsx`
- Tests: `tests/unit/test_question_relay_unwired.py`, `web/tests/unit/fleetRelay.test.ts`
