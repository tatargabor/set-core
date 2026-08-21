## Why

**A reboot empties the fleet screen, and nothing in the framework remembers what was on it.**
The agent list is discovered from live process state — `/proc/<pid>/comm` for identity,
`/proc/<pid>/cwd` for the project, plus the runtime's per-session record under
`~/.claude/sessions/<pid>.json`. A boot destroys all three. What the user loses is not a
view preference but the *composition of their working session*: which agents were on which
project, and therefore which conversations to resume.

**The obvious fallback does not exist, and this is measured rather than assumed.** On this
machine, 2026-08-21: `~/.claude/sessions` held **25 records against 25 live pids, zero
stale** — the runtime removes a record when its session exits. So the records are not a
post-reboot history, and even if a crash left some behind, a pid is reused, which makes the
filename an unreliable key for exactly the case this change is about.

What *does* survive is the runtime's transcript, one file per session under
`~/.claude/projects/<slug>/<sessionId>.jsonl`, and the framework already knows how to
resume one. So the missing piece is not the resume — it is a **recorded fact of what was
loaded**, written while the agents were still there.

## What Changes

- **The framework writes a durable per-project snapshot of the agents it has seen.** Each
  entry carries identity only: session id, label/name, cwd, kind, first-seen and last-seen
  times. It is written as discovery runs, so the record is made while the evidence is live
  rather than reconstructed afterwards from whatever happens to be left.
- **The snapshot states its own limits.** An entry says when it was last seen and whether a
  resumable transcript exists for it *now*. An agent whose transcript is gone is shown as
  such — not omitted, because a silently shortened list reads as "that is all there was".
- **A restore act, per project, one button, that brings back the whole previous list.** For
  each snapshot entry it starts an agent under the owner service and resumes that session.
  Per-agent selection is deliberately not offered: the user asked for the list back, and a
  restore of a subset is a different act that can be added later without changing this one.
- **A restore is reported per entry, never as a single success.** Started, skipped-because-
  already-live, skipped-because-no-transcript, failed — each with its reason. A restore
  where 3 of 9 came back must not render as "restored".
- **The existing refusal to resume a live session is kept, not bypassed.** `owner.recover()`
  refuses to resume a session a live process is bound to, because a resume against a live
  session forks its conversation silently. Restore skips such an entry and says so.
- **A new HTTP route, because there is none.** `POST /api/fleet/agents` deliberately takes
  no `argv`, and the resume machinery (`fleet/owner.py:recover`, `OwnerClient.recover`) is
  reachable only from the owner socket. Restore gets its own route rather than a free-form
  parameter on the start route.

## Capabilities

### New Capabilities

- `agent-fleet-snapshot`: the framework durably records, per project, the identity of every
  agent discovery has seen — session id, label, cwd, kind, first- and last-seen — so that a
  list which no longer exists in process state is a recorded fact rather than an inference.
  The record carries identity only: no transcript content and nothing derived from a
  project's domain.
- `agent-fleet-restore`: a per-project act that brings the recorded list back by starting an
  agent and resuming its session for each entry, reporting the outcome of every entry
  separately, and refusing — rather than forking — a session that is already live.

### Modified Capabilities

<!-- None, and this is a measurement rather than an omission.

     The capability that would own the write side, `agent-fleet-inventory`, is defined in the
     `fleet-view` change and has NOT been archived (checked 2026-08-21: `ls openspec/specs/ |
     grep -i fleet` → `fleet-dockable-views`, `fleet-panel-dividers` only). There is no
     `openspec/specs/agent-fleet-inventory/spec.md` to write a delta against, so a delta here
     would name a spec that does not exist.

     What this change does to inventory is additive and does not alter any requirement it
     states: discovery keeps reporting exactly what it reports today, and the snapshot is
     written from that answer. Recorded so the next reader does not mistake the empty section
     for "nobody checked". -->

## Impact

- **`lib/set_orch/fleet/`** — a new snapshot module (write + read + prune) and a new restore
  module. Both stay domain-free: they handle identity, not project content.
- **`lib/set_orch/fleet/discovery.py`** — the call site that hands each discovery answer to
  the snapshot writer. Discovery's own return value is unchanged.
- **`lib/set_orch/api/fleet.py`** — a route to read a project's snapshot and a route to
  restore it, plus their per-entry outcome payload.
- **`lib/set_orch/fleet/owner.py` / `ownerd.py`** — unchanged. The owner service stays thin;
  every restart of it kills every agent it holds, so no restore logic lands there. Restore
  calls the existing `recover` over `OwnerClient`.
- **`web/src`** — the fleet screen gains the restore affordance for a project whose snapshot
  is non-empty, and the per-entry outcome report.
- **Storage** — one new durable file under the framework's per-user store. Nothing derived
  from consumer data beyond identity is written to it.
- **No production deploy path is touched**, and nothing here executes a deployment.
