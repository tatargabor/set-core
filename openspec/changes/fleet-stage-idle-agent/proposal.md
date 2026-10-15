## Why

The fleet screen marked every live agent with the amber `⚠ stage?` gap (`join-failed`):
measured 2026-10-15, four agents across two projects, not one resolved and not one
working a change the screen could not find. The resolver chose `join-failed` over
`nothing-started` whenever the PROJECT had any un-archived change directory, and real
projects keep dozens of them (70 and 41 on the day). So `nothing-started` was
unreachable, an agent doing work outside any change was reported as a failed match, and
a genuine join failure became indistinguishable from every other row. Registered as
B-162.

## What Changes

- The choice between `nothing-started` and `join-failed` is made from evidence about
  THIS agent, not from the project's tree: an agent whose own session record was read
  and addresses no change (and has no running work-cycle record) is `nothing-started`,
  whatever the project holds.
- `join-failed` keeps its meaning — work could not be matched to this agent — for the
  two cases where that is what happened: the agent named a change the producer's index
  does not carry, or the agent's session record could not be read at all while the
  project has work in flight.
- The strip's tooltips say what each gap means about the agent.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `agent-stage-derivation`: the rule that separates an idle agent from an unmatched one.

## Impact

- `lib/set_orch/fleet/stage.py` (Layer 1) — `resolve_stage`, both paths.
- `web/src/components/AgentStageStrip.tsx` — tooltip text only.
- No payload shape change: the same two reason values, chosen differently.
