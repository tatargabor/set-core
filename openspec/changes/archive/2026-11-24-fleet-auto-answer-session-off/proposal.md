## Why

Automatic answers are one machine-wide switch. The owner works at one agent while the rest of
the fleet runs unattended, and at that agent the decider answering for him is exactly wrong
(owner, 2026-11-24: *„amelyik agentben vagyok tudjak olyat hogy ott auto answer nem megy mert
pl pont tervezek vagy valami és odalépve nem akarom hogy auto answer legyen"*). Today the only
choice is turning automatic answers off for every agent.

## What Changes

- An **agent-level opt-out**: automatic answers stay on machine-wide and are off for the
  agents named. An agent is named by its fleet terminal label, so the opt-out survives the
  session's `/clear`. A session outside the fleet is named by its session id.
- For an opted-out agent the decider does nothing: the relay's question goes to the operator's
  channel byte for byte, as with the switch off, and no continuation is decided for it. The
  switch-on pull-in starts no decide-only worker for it.
- Controls: an icon toggle in the fleet terminal's header ("auto-answer off here"), the list
  on the automatic-answer panel with a way to turn each back on, and
  `set-auto-answer here off|on|status`, run from inside the session (`! set-auto-answer here off`).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `fleet-auto-answer`: a requirement for the agent-level opt-out.

## Impact

- `lib/set_orch/fleet/auto_answer.py` (the off list and its lookup), `auto_answer_worker.py`
  (the outbound honours it), `relay_backfill.py` (no decide-only worker for such an agent),
  `api/fleet.py` (state + toggle), `bin/set-auto-answer` (`here`).
- `web/src/components/FleetTerminal.tsx` (header toggle), `FleetAutoAnswer.tsx` (the list).
- Machine-local config key `auto_answer.off_agents` (a JSON list of `label:<label>` /
  `session:<id>`), never in a repository.
