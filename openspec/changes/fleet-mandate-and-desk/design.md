## Context

Three facts about the running system shape everything below. Each was read from the code on
2026-11-23 and the place is named, so it can be re-checked in seconds rather than re-derived.

1. **The agent owner persists nothing, on purpose** (`lib/set_orch/fleet/owner.py`, module
   docstring: "Nothing is persisted … a line of business logic added here is a future outage of
   every running agent"). `OwnedAgent.requested_by` therefore dies with the owner process, and
   `restore.py` passes a label and a session id only. The roster (`fleet/roster.py`) is the
   durable half, and it is written by the dashboard service.
2. **A started agent is never told anything.** The start body forbids extra fields and the argv
   is fixed (`fleet/ownerd.py`). The agent does not know its own label. The only way to brief it
   is `POST /api/fleet/agents/{pid}/instruct`, which sends over the bus and therefore needs a
   seat the agent may not have yet.
3. **The bus already resolves a fleet label as an address.** `set-agent-comm` reads the fleet
   roster on every send and turns a label into the seat that holds it now (its
   `resolveAddressees`). What it does not have is a preferred session per project: a bare
   project name with a `REQUEST` wakes every live session of that project (its `wakes` rule),
   and it has no production caller for "requests this seat sent that nobody answered".

The assessment of the bus that the operator asked for follows from 3: **keep it.** It is the
transport, it is tested (about 400 tests), and the two things missing are a routing rule and a
state the fleet can supply. Replacing it would re-solve delivery, rooms, liveness and the relay
to gain neither. The native cross-session channel of the runtime reaches every live session,
but it is a channel without rooms, history or a record, and it cannot start anything.

## Goals / Non-Goals

**Goals:**

- An agent's reason for existing is a record the framework wrote, visible without opening the
  agent, and present in the agent's context after every clear and compaction.
- A request to another project reaches one session that is there *for* that purpose, started
  when it is not there, with no person opening anything.
- Whether a request was answered is a fact the screen can show.
- The relations are drawn: who exists for what, who is working for whom, what is still open.

**Non-Goals:**

- No change inside `set-agent-comm`. Four improvements are requested from it (D9); every
  requirement here holds without them.
- No second transport. An agent that cannot be reached on the bus is offered enrolment.
- No engine-evidence closure and no session rotation — they stay in
  `agent-goal-and-lifecycle`, reading the record defined here.
- No resumed desk sessions, no dispatcher, no automatic mandate inference from a transcript.

## Decisions

### D1 — The mandate is written by the dashboard service, keyed by its own id

The record lives in a machine-local file under the per-user **state** directory, beside the
idle-close log, written atomically under a lock by the API handler that performs the start. Not
by the owner: fact 1. Not keyed by label: a label is reused over time and renamed. Not keyed by
session id: the session does not exist yet at the moment of the act, which is the only moment
the relation "who asked for this, and why" can be captured.

Fields: `id`, `kind`, `goal`, `scope` (paths, optional change name), `done_when`,
`requested_by` (a seat, or the operator) with `is_claim`, `project`, `cwd`, `label`, `unit`,
observed `session_ids`, `source` (`start` or `declared`), `delivered`, `declared_at`, `closed`.

*Alternative considered:* the engine's unit record (`purpose.py`). Rejected: it exists only for
work run as units, and on a machine with no engine that is no agent at all — measured, `purpose`
is null for 15 of 15.

### D2 — Two kinds, and no third until one resolves to different behaviour

`work` — a piece of work, started by a person or by another agent. `desk` — the session that
answers for a project. The kinds differ in three behaviours (who may be addressed by a project
request, the opening line, the stop rule), which is the test for a kind being real. Lane names
(feature, bugfix, chore) are not kinds here; they belong to the capability that owns that
vocabulary and can be added to `scope` when something reads them.

### D3 — A start by an agent needs a goal; a start by the person may have none

An agent-requested start (`requested_by` present) with an empty goal is refused. A start from
the screen may leave the goal empty and is recorded with **no mandate**.

This departs from the earlier design, which refused every start without a goal. The reason is
fail direction: a person who only wants a terminal will type a placeholder, and a placeholder
goal is a false value — it reads as a declared purpose on the tile and on the map forever. An
honest gap, marked, is the smaller lie. An agent has no such excuse: it starts a peer *for*
something, and that something is exactly what is being lost today.

### D4 — The agent is told its mandate through launch-time settings, not a prompt

The owner starts the child with two additions and nothing else: an environment variable naming
the mandate id (and one naming the label), and `--settings` carrying a `SessionStart` hook that
prints the mandate as session-start context. The settings are passed as a JSON string from the
framework's own installation, so no file enters the project's tree.

Why this carrier: the earlier change measured that `--settings` reaches a framework-started
agent, leaves the project tree byte-identical, and **merges per key — hook lists are additive**,
so the project's own hooks still fire. And a `SessionStart` hook fires again after a clear and a
compaction, which is the property a sentence in an opening prompt cannot have.

What is NOT yet measured, and is therefore group 1 of the tasks rather than an assumption: that
`SessionStart` supplied this way fires on each of start, clear, compaction and resume; that the
hook subprocess sees the two variables; that a project's own `SessionStart` hooks still fire
beside it.

The owner's contract grows by one typed field (`mandate_id`). It still persists nothing and
still takes no free-form argv or environment from a caller.

*Alternative considered:* `--append-system-prompt`. Rejected: it fixes the text at launch, so a
mandate declared or amended later cannot reach the agent, and the text would travel through the
owner's argv into the process table.

### D5 — The first turn is a fixed opening line chosen by kind

An agent started with no first turn sits at an empty prompt; nothing on the bus can wake it,
because its bus hooks only run inside a turn. So an agent-requested `work` start and every
`desk` start pass one positional prompt — framework text selected by kind, never caller text —
telling the agent to act on the mandate in its session-start context. A start by the person
passes none; they type.

### D6 — The desk is the live agent whose mandate kind is `desk` for that project

Resolution asks one question — is there a live, framework-held agent with an open `desk`
mandate for this project? — and never inspects what other sessions are doing.

Its label is `<project>-desk`. The label is not the definition, but it buys two things that
already exist: the owner refuses a second agent with a held label, which makes "one desk per
project" an enforced invariant and turns a concurrent second start into "the desk exists"; and
the bus resolves that label as an address today. Renaming a desk is refused, and no other agent
may take a registered project's desk label.

A request is refused, with the reason, when the project is unknown, archived, or its root fails
the existing start-location check.

### D7 — `set-fleet-ask` sends as the asker; the framework never speaks for an agent

The command runs in the asking session. It asks the API to resolve the desk (starting it and
waiting, bounded, for its bus seat), then **itself** runs the bus send addressed to that seat,
then reports the entry's room and timestamp back. The entry is therefore from the asker's own
seat, and the reply returns to the asker through the bus's existing rule that a reply to your
entry wakes you.

*Alternative considered:* the API sends, as `instruct` does today. Rejected: the reply would
come back to the dashboard's identity, and a relay step would have to be built to carry it on.

When the desk never appears on the bus within the bound, the engagement fails with a named
class — the project is not on the bus, or the desk did not become ready — and the offered fix is
enrolment.

### D8 — An engagement stores a pointer, and is closed by the bus's own link

The engagement record holds the two parties, the kind, an optional short subject the asker
supplies for the map, and the request's **room and timestamp** on the bus. The request text
is not copied: one copy, on the bus, where its audience rule applies.

States: `resolving` → `open` → `answered`, or `failed` with a reason class, or `withdrawn`.
`answered` is decided by the bus's own definition — an entry by a seat of the addressed project
in the same room whose heading links to the request's timestamp — read from **entry headings
only**, the same structural confidentiality line `fleet/channels.py` already holds: the parser
stops at the heading and no body can reach the payload. An engagement open past a bound is
reported as **waiting**, which is a display state, not a transition.

An asker is bounded in open engagements (default five); the sixth is refused. That is the loop
guard: two desks asking each other can only proceed as far as the bound.

### D9 — What is asked of the bus, and why nothing here waits for it

Requested from `set-agent-comm` as its own change, in its own repository:

1. A bare project name wakes the project's desk when one is live, instead of every session.
2. Its wake filter reads the mandate, when one exists, beside the declared focus.
3. A machine-readable "open requests" surface for any seat, so D8's heading parse can be
   replaced by the bus's own answer.
4. Doorbell deliveries are counted in its statistics; today they read as "reached no session",
   which makes a working path look like a failing one.

Until 1 ships, an agent that hand-addresses a project name still wakes its sessions; the
mandate text each of them carries (D10) is what makes the misdirected ones decline.

### D10 — Scope protection is an instruction in this change, and says so

The delivered mandate ends with a standing rule: a request from another agent that falls
outside the mandate is declined once, naming the project's desk and the command that reaches
it. That is an instruction, and an instruction is not a constraint. The constraint is routing
(D9.1), and the spec states which of the two is in force rather than letting the instruction
read as a guarantee.

### D11 — The desk stops after a bounded quiet period, decided by the framework

A sweep in the dashboard service's existing lifespan stops a desk when all hold: its mandate is
open and of kind `desk`; it has no `open` or `resolving` engagement; its state is measured and
quiet; and its last movement is measured and older than the bound (default thirty minutes,
configurable). Any unmeasured input keeps the desk — a desk left running costs a seat, a desk
stopped mid-answer costs the answer. The stop closes the mandate with the reason.

The idle-close rule does not cover this: it keys on time since human input, which a desk never
has, and it deliberately keeps an agent whose idle time is unmeasured.

### D12 — The map is one payload and one dockable view, on the library already bundled

`GET /api/fleet/map` returns project groups (only those with a live agent or an open
engagement are expanded), agent nodes with their mandate, and three edge kinds that are never
drawn alike: **engagement** (with state and age), **started** (the recorded requester, marked
as a claim), and **flow** (the declared project relation, as background). The web bundle
already carries a node-graph library, so the view adds no dependency.

Two markers are not optional: an agent with no mandate, and an engagement that is waiting or
failed. Their counts sit on the view's opener, so a collapsed map cannot hide them.

### D13 — Flows adopt the shape an existing project map already uses

A project map maintained by hand in one of the operator's repositories describes each relation
as `{to, what, how}`. That shape is adopted as-is rather than inventing a parallel one: the
role file gains an optional `flows` list per project, and the generated rule renders each as
"for *what*, ask *to* (*how*)" with the command. The existing visibility rule applies
unchanged: a public repository's rule counts a private neighbour and does not name it.

### D14 — The parent claim follows the API, and the mandate carries it

The inventory calls a recorded requester a claim and a process ancestor measured; the screen
has the two reversed. The screen is corrected, and `parent` is read from the mandate when the
owner no longer holds the agent — which makes the relation survive an owner restart for the
first time.

## Risks / Trade-offs

- **A desk started for every stray request burns sessions** → the label invariant caps it at
  one per project, the quiet-period stop reclaims it, and an asker is bounded in open
  engagements.
- **The mandate text is the operator's words and may name a client** → stored only under the
  per-user state directory with owner-only permissions, never logged (log lines carry ids,
  kinds and classes), never written into a repository, and absent from every committed fixture.
- **The `--settings` carrier collides with a project's own status line or hooks** → hooks were
  measured additive; this change supplies a hook only and no status line. Re-measured in
  group 1 for `SessionStart` specifically.
- **A desk in a project that is not on the bus can be started but never reached** → resolution
  checks enrolment before starting and fails the engagement with that class instead of leaving a
  silent agent behind.
- **Heading-only parsing drifts from the bus's heading format** → held by a test built from the
  bus's own writer output, and replaced by the bus's surface when D9.3 ships.
- **Two records of "who asked"** (owner memory, mandate) → the mandate is the source; the owner
  field is kept for the live join only and never preferred when they disagree.

## Migration Plan

1. Ship the record and the read paths first; every existing agent reports "no mandate", which
   is the truth.
2. Ship delivery and the start form; restart the owner once, when no agent it holds is working.
3. Ship desk resolution, `set-fleet-ask` and engagements; regenerate the role rules so agents
   learn the command.
4. Ship the map.

Rollback at any stage is removal of the stage: the two state files are additive and nothing
else reads them.

## Open Questions

- Whether a person may appoint an already-running session as a project's desk. Left out: it
  needs a mandate declared after the fact *and* delivered, and delivery to a running session
  has no carrier yet.
- Whether a fresh desk should be handed the previous engagements between the same pair. Not
  until someone is measured asking the same question twice.
