## Context

The fleet screen holds three different names for one agent, and until the first reboot
nothing forced them to disagree.

| name | where it lives | who chose it | lifetime |
|---|---|---|---|
| **label** | the owner service's map, and the systemd scope name derived from it | the person who started the agent | the agent's |
| **derived name** | the runtime's own per-pid session record, field `name`, `nameSource: "derived"` | the runtime, from the cwd plus two random hex characters | that process's |
| **key** | the durable record, keyed on session id | nobody — it is the session id | forever |

Discovery reads the runtime's record, so `agent.name` is the *derived* name. The durable
record stores `agent.name`. The owner's label is never asked for. While every agent runs,
this is invisible: nothing displays both at once, and the label is what the tab strip shows
because it comes from a different call.

A reboot separates them, and a resume separates them again. Measured 2026-08-21, after the
first real one: eight agents came back, and for each of them the record had stored the
*previous* derived name, so the restore started them under that; then the resumed session
derived a *new* name, which the screen shows in the tile header. So the record holds name A,
the framework holds name A, the screen shows name B, and the name the person actually chose —
which was neither — is gone. A docked panel, keyed on the label, points at a name nothing
holds and correctly reports an empty panel.

The second half of the problem is that nothing can be fixed afterwards: **there is no rename**.
The names the user chose still exist in the owner's log, and each session is identifiable by
its transcript, so the mapping is reconstructible by a human — but there is no operation that
would apply it.

## Goals / Non-Goals

**Goals:**
- The name a person chooses is the name the framework stores, restores and displays.
- An agent can be renamed while it runs, so names lost before this change can be put back by
  hand, and so a name is not a decision that has to be right the first time.
- One identity on screen for a framework-held agent, so that no control keys on something
  other than what the reader is looking at.
- A dock follows its agent through a rename and through a restore.

**Non-Goals:**
- Reconstructing the lost mapping automatically. The framework cannot know which conversation
  a person called `bugfix`. It can only make the correction possible and durable.
- Renaming an agent the framework does not hold. The name belongs to the runtime, in a file
  the runtime owns and rewrites.
- Any change to what an agent *is* — session id, transcript, cwd and project stay untouched.

## Decisions

### D1 — The record stores the owner's label, and an unknown label stays unknown

`roster._entry_from` reads `agent.name`. It will take the framework's label instead, looked up
by pid from the same `OwnerClient().list_agents()` answer the API already fetches once per
listing.

The alternative — store both and let the reader choose — was rejected: two names in one entry
is the divergence this change exists to end, one layer down. A restore would then have to pick
one, which is the same decision made in a place with less information.

**An unknown label is written as unknown**, never backfilled from the derived name. This is
the false-value rule: an invented label renders exactly like a chosen one, and the person who
sees `set-core-c6` in a tab has no way to tell that nobody named it that. The cost is honest —
a restore of a never-held agent says its name was derived.

**When the owner cannot be asked**, an existing entry keeps the label it has and a new entry is
written with an unknown label. Overwriting a known label with "unknown" because a socket was
briefly unreachable would destroy the exact thing this change is protecting.

### D2 — The scope unit becomes a stored fact; `unit_name(label)` is a start-time function only

This is the decision that makes a rename cheap, and it is the reason the change is not a
one-line roster fix.

Today `scopes.unit_name(label)` is called wherever a unit is needed — stop, recover, status.
That welds the systemd unit name to the display name: systemd cannot rename a unit, so
changing the label would mean stopping the scope and starting a new one, i.e. killing the
agent's in-flight turn and its terminal history to edit a string.

`OwnedAgent` already carries `unit`. The change is to *use* it everywhere and to stop
re-deriving. `unit_name()` stays as the function that chooses a unit name at start time.

Alternative considered: keep deriving, and implement rename as stop + resume. Rejected —
it makes the rename destructive, which is precisely what makes it unusable for the case that
prompted it (seven live agents, one of them holding an unsent draft in its prompt).

Consequence to watch, and it is why the spec has a scenario for it: after a rename the unit
name no longer matches the label, so any code that re-derives is now *wrong* rather than
merely redundant, and it fails by acting on a unit that does not exist — which systemd reports
as "no such unit", a message that reads like the agent is gone.

### D3 — Rename refuses a collision; restore derives one. The asymmetry is deliberate

A person renaming an agent is looking at the screen: a name they did not choose appearing
instead is a false value they have no reason to question, so the framework refuses and says
who holds the name. A restore runs over a whole list with nobody watching: refusing would lose
the agent, so it derives a free variant **and reports the rename in the outcome**.

Both halves already exist in `restore._free_label`; what is added is that the outcome
distinguishes *restored under its own name*, *renamed because the name was taken*, and
*derived because no name was recorded*. Today all three read as `started`.

### D4 — The rename is an owner operation, because the owner holds the map

The owner's map is keyed by label. A rename is a re-key of that map plus a write to the
durable record. It is not business logic — it adds no policy, no decision and no persistence
to the owner — so it does not violate the thin-owner rule that `owner.py` states, and it
cannot be done anywhere else: no other process holds that map.

The HTTP surface is `POST /api/fleet/agents/{label}/rename`, addressed by label like `stop`,
for the reason `stop` gives: a pid is reused, a label is what the framework named.

### D5 — The screen shows the framework's label when there is one

`_agent_payload` will present one identity: the label for a `started-here` agent, the runtime's
name for a `foreign` one. Today it sends both `name` and `terminal_label` and the tile header
renders `name`, which is how one agent's displayed name came to be another agent's terminal
label on this machine.

The runtime's name is not dropped from the payload — a `foreign` agent has nothing else — but
it stops being what a held agent is called.

### D6 — The dock follows the label because the rename tells it to

`fleet-layout.json` stores `docks: {project: [{kind, id, edge}]}` where `id` is a terminal
label. The rename updates that document as part of the operation, so the dock follows.

Alternative considered: key the dock on the session id instead. Rejected for now — the dock
can hold panels that are not agents (`kind` is already a discriminator), and a session id is
not an address any control uses. Revisit if a second identity-carrying panel appears.

The restore side needs no dock change once D1 lands: the agent comes back under the recorded
label, which is the id the dock already holds.

## Risks / Trade-offs

- **A re-derived unit name somewhere this change misses** → after a rename that call acts on a
  unit that does not exist and reports the agent as gone. Mitigation: `unit_name` gets exactly
  one legitimate caller (start), and a test asserts that a renamed agent is still stopped by
  its original unit.
- **The rename re-keys a live map while a terminal relay is attached to the old key** →
  a viewer could be left holding a socket for a name that no longer exists. Mitigation: the
  relay resolves the agent once at attach; the spec requires the old label to stop resolving,
  and an attached viewer is expected to reconnect under the new name.
- **The record now depends on the owner being reachable** → a restore after a long
  owner outage could store fewer labels. Mitigation: D1's rule that an existing label is never
  overwritten by an unknown, so an outage costs nothing already recorded.
- **Names already lost cannot be recovered by any code here** → the change delivers the
  mechanism, and the correction is a human act. Stated in the tasks rather than left implied.

## Migration Plan

1. Land D2 (stored unit) first, with the stop and recover paths using it. This is invisible
   behaviour-preserving refactoring and is the precondition for a non-destructive rename.
2. Land the rename (D4, D3's refusal half, D6's dock update, D5's single identity).
3. Land D1 (the record stores the label) — after rename, so that the names put back by hand
   are the ones the record starts storing.
4. Then, as an operational act and not part of this change's code: rename the currently
   running agents back to the names their people gave them, using the transcript to identify
   each one.

Rollback: each step is independent and additive. The record's label field does not change
shape, so an older reader is unaffected.

## Open Questions

- Should a rename be offered for an agent whose scope this framework started but whose owner
  has since restarted (an orphan)? Its terminal is gone, so there is no map entry to re-key —
  probably it belongs to recovery rather than to rename, but the surface should not simply be
  silent about it.
