## Why

The first real reboot happened on 2026-08-21, and the restore this framework built for it
worked: 8 agents came back, every recorded entry got a stated outcome. What did **not** come
back was the thing the user actually navigates by — the **name**. The roster stores the
runtime's own generated name (`nameSource: "derived"` in `~/.claude/sessions/<pid>.json`),
not the label the user typed when they started the agent. So `set-core-bugfix`,
`set-core-restart` and `consumer-app-tools` returned as `set-core-34`, `set-core-bb`,
`set-core-e2`; the docked right-hand panel, which is keyed on the label, came back empty;
and a resumed session then derives a *third* name, so the screen shows one identity while
every control keys on another. Measured, and registered as B-45, B-46, B-47.

A name is not decoration here. It is the only handle a person has on eight identical-looking
sessions, it is what the dock, the stop action, the terminal socket and the recovery path all
address, and it is the one part of an agent that a reboot ought to be able to give back
intact — because unlike a pty, a name costs nothing to write down.

The same defect has a second half, which is why this change is not a one-line fix to the
roster: **there is no way to rename an agent at all.** A name typed once is a name forever,
and today changing it would mean stopping the agent and resuming it — killing the in-flight
turn and the scrollback to edit a string. The user asked for both, in one breath: keep the
names across a restart, and let them be changed afterwards.

## What Changes

- **The roster records the label the framework HOLDS, not the name the runtime derived.**
  The owner's `label` is the identity every control uses; the runtime's `name` is a generated
  string that changes on every resume. The roster asks the owner, and records what it gets.
- **A label the framework does not know is recorded as unknown** — never filled in from the
  derived name. A restore of an agent the framework did not start has no label to give back,
  and saying so is different from inventing one that will look deliberate on screen.
- **Restore gives the recorded label back**, so the tab strip, the dock and the stop action
  address the same agent after a reboot as before it.
- **An agent can be RENAMED while it runs.** New operation, and the design decision that
  makes it possible is in the next bullet.
- **The owner stores the scope unit as a fact instead of deriving it from the label.**
  Today `scopes.unit_name(label)` is recomputed wherever the unit is needed, which welds the
  systemd unit name to the display name: a rename would have to stop and re-create the scope,
  which kills the agent's current turn and its terminal history. A stored unit makes a rename
  a metadata change that the running agent never notices. **BREAKING** for any caller that
  re-derives a unit from a label.
- **One identity on screen.** The fleet surface shows the framework's label for an agent the
  framework holds, and the runtime's name only for one it does not — so a displayed name can
  no longer be another agent's terminal label, which it currently is on this machine.
- **A dock survives a rename as well as a reboot**, because the dock and the agent agree on
  what the agent is called.

## Capabilities

### New Capabilities
- `agent-terminal-rename`: changing the name of a running framework-held agent without
  interrupting it — what may be renamed, what a name collision does, what the surface reports,
  and what must NOT happen (a stop, a resume, a lost turn, a second agent under the old name).

### Modified Capabilities
- `agent-fleet-snapshot`: the recorded entry's `label` becomes the framework's own label
  rather than the discovered name, and an unknown label is recorded as unknown rather than
  filled in.
- `agent-fleet-restore`: a restored agent comes back under its recorded label, and the
  outcome states the label it came back as.
- `fleet-dockable-views`: a docked view follows its agent across a rename and a restore,
  and the "no running agent with this terminal" state is reserved for an agent that is
  genuinely absent.

## Impact

- `lib/set_orch/fleet/roster.py` — what an entry's `label` is read from; the entry contract.
- `lib/set_orch/fleet/owner.py`, `ownerd.py`, `owner_client.py` — the unit as a stored fact,
  and the rename operation over the owner socket.
- `lib/set_orch/fleet/scopes.py` — `unit_name()` stops being the way callers find a unit.
- `lib/set_orch/fleet/restore.py` — the label it asks for and the outcome it reports.
- `lib/set_orch/api/fleet.py` — the rename route; which identity `_agent_payload` presents.
- `web/src/pages/Fleet.tsx`, `components/TileControls.tsx` — the rename control and the one
  displayed identity.
- Bug register entries B-45, B-46, B-47 close with this change.
- No consumer project is touched, and nothing here deploys.
