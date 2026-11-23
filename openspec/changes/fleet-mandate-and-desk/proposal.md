## Why

The fleet can say that an agent is alive and what it is doing. It cannot say **why the agent
exists**, **who it works for**, or **which session answers for a project** — and those three
gaps are what the operator pays for every day, by hand.

Measured on the operator's machine on 2026-11-23, with the dashboard, the agent owner and the
bus all running:

- **15 live agents, 12 of them started through the fleet. None carries a recorded goal.** The
  start request takes a label, a directory, a requester, a provider and a model — nothing about
  what the agent is for. The label is the only trace, and half of the labels are a clock stamp.
- **Who asked is recorded for 2 of 15**, and that record lives in the owner's memory only: it
  is lost when the owner restarts and is not carried by a restore.
- **4 of 15 declared a focus on the bus**, which is the agent's own sentence and goes stale.
- **Two weeks of bus traffic: 1237 entries, 951 of them to another project. 58 % were addressed
  to a project NAME**, which the bus delivers to every live session of that project. A request
  therefore lands on whichever agent happens to be open there — one in the middle of unrelated
  work — and on nobody at all when the project has no session.
- **379 cross-project requests and questions; 44 (12 %) have a reply linked to them.** For 250
  the addressed project wrote *something* in the room within a day, and nothing can tell whether
  that was the answer. For 85 (22 %) nothing came within a day. The bus has no notion of an open
  request between two agents, so neither does the screen.
- **No agent-facing instruction says how to reach another project.** The operator tells each
  agent by hand: open that project, wait on the bus, then talk.

The earlier attempt at the first gap is `agent-goal-and-lifecycle`: 4 of 78 tasks done, all four
of them measurements, stalled since 2026-08-19 because its closure half waits on an engine that
has not run here in a month. Its record half does not depend on that engine and is the part
everything below needs, so this change takes it over rather than letting it wait a fourth time.

## What Changes

- **A started agent carries a mandate, and the mandate is a framework record.** Goal, kind,
  scope, who asked, and what closes it — written durably at the moment of the start by the
  service that outlives the agents, not by the owner (which persists nothing by design) and not
  as a sentence in an opening prompt. A start requested by another agent without a goal is
  refused. A start by the person at the screen may leave the goal empty, and that is recorded
  as "no mandate" rather than filled with a placeholder.
- **A hand-opened agent has no mandate, says so, and can be given one.** Declaring it later is a
  record for the screen; the agent is told only where a carrier exists, and the tile says which.
- **The agent is told its mandate by the framework, at every session start.** Through settings
  the framework supplies at launch from its own path — a carrier already measured to reach a
  started agent without writing a file into the project's tree — so the mandate survives a
  clear and a compaction instead of scrolling out of the context.
- **Every project has a desk: the one session that answers for it.** A request to a project
  goes to its desk. If the desk is live it is used; if it is not, the fleet starts one with the
  request as its mandate. A session doing other work is never picked because it happens to be
  open. A desk with no open request stops itself after a bounded quiet period.
- **Reaching another project is one command.** `set-fleet-ask <project> "<request>"` resolves
  the desk, starts it when needed, sends the request over the existing bus as the asker, and
  records the engagement. It replaces "open that project by hand and wait".
- **An engagement is a record: who asked whom for what, and whether it was answered.** Closed by
  a reply the bus itself links to the request — never by an agent saying it is done. An
  engagement that stays open past a bound is shown as waiting, on the screen and to the asker.
- **A map view draws it.** Projects as groups, their live agents inside with the mandate in one
  line, engagements as edges with their state, the start relation as a second kind of edge, and
  the declared project relations as the background. An agent with no mandate and an engagement
  nobody answered are marked where the reader is standing.
- **The project role rule says how to reach the neighbours.** The machine-local role file gains
  the flows between projects — what goes to whom, and how — and the generated rule turns them
  into "for this, ask that project", with the one command to do it.
- **The parent claim is corrected.** The inventory marks a recorded requester as a claim and a
  process ancestor as measured; the screen currently renders the two the other way round.

Deliberately **out of scope**, and named so a later reader can tell *scheduled* from
*forgotten*:

- Changes inside the bus (`set-agent-comm`): routing a bare project name to the desk, feeding
  the mandate to its wake filter, an open-requests surface for any seat, and counting doorbell
  deliveries in its statistics. They are requested from that project and this change works
  without them.
- Closing a mandate by engine evidence and rotating a session in place — both stay in
  `agent-goal-and-lifecycle`, which now reads the mandate record defined here.
- Resuming a previous desk session instead of starting a fresh one.
- A wave dispatcher that hands out mandates on its own.

## Capabilities

### New Capabilities

- `agent-mandate-record`: the durable record of why an agent was started — goal, kind, scope,
  requester, closing condition — written in the act of starting, declared later for an agent the
  framework did not start, delivered to the agent at every session start, and reported as absent
  rather than invented.
- `project-desk`: the one session that answers for a project — how a request finds it, when the
  framework starts it, what it is told, and when it stops.
- `agent-engagement-record`: the record of one agent asking another for something — its
  parties, its request on the bus, and its state, closed only by a linked reply.
- `fleet-relation-map`: the view that draws projects, agents with their mandates, engagements
  and start relations, and marks what is missing or unanswered.

### Modified Capabilities

- `project-role-rule`: the role file may declare flows between projects, and the generated rule
  renders them as when and how to reach each neighbour.

## Impact

- **CORE** `lib/set_orch/fleet/`: new `mandate.py` (record and store), `desk.py` (resolution),
  `engagement.py` (record, closure from bus headings); `owner.py` / `ownerd.py` accept a mandate
  id and the framework settings path for the child, and nothing else — the owner still persists
  nothing. `restore.py` carries the mandate across a restore.
- **API** `lib/set_orch/api/fleet.py`: the start body gains a typed `mandate`; new routes for
  declaring a mandate, resolving a desk, recording and listing engagements, and the map payload;
  the inventory carries `mandate` per agent.
- **CLI** `bin/set-fleet-ask`, `bin/set-fleet-mandate`.
- **WEB** `web/src`: a goal field on the start form, the mandate on the tile, a dockable map
  view built on the graph library already in the bundle, and the corrected parent claim.
- **Role rule** `lib/set_orch/project_roles.py`, `templates/project-roles.example.yaml`.
- **Other changes**: `agent-goal-and-lifecycle` loses its `agent-goal-record` capability to this
  change and keeps closure and rotation.
- **Stored data**: two machine-local files under the per-user state directory. They hold the
  operator's own words about work and are never logged, committed or shipped.
- **Services**: set-web restarts to serve the new routes; the agent owner restarts once for the
  new start field, when no agent it holds is working.
