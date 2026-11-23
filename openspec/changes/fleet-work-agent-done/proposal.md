## Why

An agent started by another agent for one piece of work stays open after the work is done (B-205,
reported 2026-11-22 by a consumer-family session, relaying the owner: *„azt csinaljuk meg hogy miért
nem zarodtal be ha megvolt a válasz. eza fleetben nyitott agent hiányossága"*). In the measured case the
agent answered its three questions, kept an inbox watch open and waited. Only the daily idle-close
could end it, and that keys on 48 hours without OWNER input, which an agent-started agent never
receives. Until then every bus entry woke it, and each wake re-read its whole context.

`fleet-mandate-and-desk` gives every agent-started agent a `work` mandate with a requester and a
`done_when`, and it stops a quiet desk on its own. It leaves one gap: nothing ends a `work` agent when
its work is over. This change fills that gap and builds on the mandate record. It adds no lifetime field
beside it.

## What Changes

- **A done step for a `work` agent:** `set-fleet-mandate done "<one line>"`. The agent runs it as its
  last act. It posts the line to the requester seat on the bus, marks the mandate ended with the new
  reason `agent-done`, and then stops the agent's own label through the existing stop route. The roster
  keeps the session resumable.
- **`agent-done` is a claim, not a fulfilment.** The mandate is marked ended, never fulfilled. Deciding
  from evidence whether the work was actually done stays with `agent-goal-closure`, whose rule (*a goal
  is closed by checkable evidence, never by the agent's report*) is unchanged.
- **The agent is told about the done step.** The mandate delivered at session start adds one line for an
  agent-requested `work` mandate: when the work is done, answer the requester, then run the done step.
- **Idle-close gets a short bound for agent-requested `work` agents** that have had no owner input since
  their start. It is counted from the last movement, and the default is 2 hours (local config
  `fleet_idle_close_work_hours`). Owner input after the start turns the agent into the owner's window,
  and the 48-hour rule applies again. Anything unmeasured keeps the agent, as before.

## Capabilities

### New Capabilities
- `fleet-work-agent-done`: how an agent-requested `work` agent ends — the done step, what it records,
  what it tells the requester, and the idle bound that catches one that never runs it.

## IN SCOPE
- The `done` verb of `set-fleet-mandate`, and the `agent-done` end reason
- The one-line done instruction in the delivered mandate
- The short idle-close bound for agent-requested `work` agents without owner input

## OUT OF SCOPE
- Deciding that work was fulfilled (`agent-goal-closure`)
- Desks: `fleet-mandate-and-desk` already stops a quiet desk
- Agents the person started at the screen, and agents with no mandate: unchanged
- The starter's own brief text, which is the requesting project's own content

## Depends on
- `fleet-mandate-and-desk`: the mandate record, `MandateStore.end`, `set-fleet-mandate`, and the
  mandate delivery at session start. This change is applied after those are committed.
