## Why

An agent is started and nothing records **why**. The framework can say what an agent is doing —
`fleet-view` reads that from its session log — but not what it was started *for*, so it cannot say
whether the work is finished, and neither can the screen. What follows from that absence is the
whole cost: an agent that has completed its work looks exactly like one that has stalled, and a
person has to open it to tell the difference.

**This half was already handed over once and dropped in transit.** `fleet-view/tasks.md:15` records
that five things moved to `work-cycle-engine-apply-first`, among them *"the goal and progress an
agent reports"*. Progress arrived — `AC-29` requires it to be derived from completed task markers
and never from a turn count. The goal did not: `grep -riE 'goal' openspec/changes/work-cycle-engine-
apply-first/specs/` returns **0**. One line claims the goal found an owner and it found none. Left
alone it evaporates a third time.

Two measurements taken on 2026-08-19 (`measurements.md`) decide the shape, and both reverse the
assumption the work started from.

- **An agent whose context fills does not have to be replaced.** `/clear` rotates the session id and
  the transcript **inside the same process**: measured pid 1701204 before and after, `/proc/<pid>/stat`
  starttime token unchanged, one transcript before the clear and two after. So the "start a successor
  and hand off to it" branch is not needed — the pty the framework already owns can carry the clear,
  and the process, the label and the fleet tile survive it.
- **Remaining context is already measured, per model, by the harness.** It hands the **statusline
  command** — and, measured, no hook at all — `context_window: {context_window_size,
  used_percentage, remaining_percentage, …}`, with the size stated per model. Nothing has to ask the
  agent how full it is, and no constant is needed. *(An earlier draft of this line said "a hook".
  Nine were registered and eight fired; `context_window` appears in the statusline payload alone.)*

## What Changes

- **An agent is started with a declared goal, and the declaration is a framework record.** Not a
  sentence in the opening prompt, which is unreadable afterwards and unfalsifiable. The record exists
  before the agent does — the framework writes it at the moment of the act, the same shape
  `fleet-view` task 2.5 arrived at for lineage (`requested_by`), and for the same measured reason: a
  relation that exists only at the moment of starting cannot be recovered later by walking anything.
- **An agent started outside the framework has NO goal, and that is reported as such.** A hand-opened
  editor window is the ordinary case, not a defect. Inferring a goal from its transcript would be the
  guessed-phase failure `fleet-view` already refuses — wrong exactly when the situation is unusual.
- **Fulfilment is closed by evidence, never by the agent's word.** `.claude/rules/evidence-discipline.md`
  states it plainly: a subagent's "done" is not evidence that anything happened. The engine already
  solved this for a work unit — a schema-constrained `GROUP_DONE` diffed against the checkmarks
  actually in `tasks.md`, in both directions. This change **reuses that verdict** and adds no second
  definition of "finished".
- **A goal the framework cannot check is declared as unverifiable, and stays open.** Some goals have
  no artifact — "talk this through with me". Reporting such an agent as complete because it said so
  would be the false-value class. It is closed by a person, and the tile says which kind it is.
- **A completed agent stops, and its record outlives it.** The stop is the point of the goal: an
  agent still holding a seat after its work is done is the orphan the fleet screen exists to expose.
  What remains is the goal record and its closing evidence — never the transcript, which
  `fleet-view` forbids persisting.
- **Session rotation in place, at a measured threshold.** When remaining context falls below a
  declared bound, the framework writes a handoff, sends `/clear` into the pty it owns, and feeds the
  handoff back. Same process, same label, same tile. The `handoff` skill already defines what the
  carried cargo is; this change does not invent a second format.
- **Rotation is offered only where the framework owns the pty.** An agent someone opened in an editor
  cannot be cleared from outside — the same kernel boundary `fleet-view` measured for input. Its tile
  says so rather than presenting a control that goes nowhere.
- **A rotation that could destroy work is refused rather than attempted.** `/clear` typed into a TUI
  mid-turn is not a rotation, it is a keystroke landing somewhere unknown. The agent must be between
  turns, and the framework must be able to tell — measured, not assumed.
- **The goal is durable, because the agent is.** Measured while writing this: the owner holds its
  agents in memory and writes nothing, and its recovery path takes no requester — while
  `scopes.py` deliberately starts each agent in its own transient scope *so that it outlives the
  service*. A goal stored the way the requester is stored would therefore vanish while its agent kept
  working, and the screen would show a running agent whose purpose the framework had forgotten. So
  the goal is written durably at the moment of the act, and a recovered agent whose goal cannot be
  restored is reported as **unrecoverable** — which is a different claim from having none.
- **This extends two records that already exist rather than adding a third.**
  `OwnedAgent.requested_by` already captures who asked, in the act, for the same measured reason; and
  `purpose.py` already answers *what an agent is working towards* from the engine's records. The goal
  is a field beside the first and a different question from the second — *why it was started*, which
  exists for every framework-started agent whether or not an engine ever ran. The boundary is written
  into the design so neither grows into the other.
- **The agent's KIND is declared, not derived.** Which lane a started agent serves — feature, bugfix,
  chore — comes from `change-lane-profiles`, which already owns that vocabulary and already forbids a
  lane that resolves to no behavioural difference. No new taxonomy is created here.

Deliberately **out of scope**: the wave dispatcher that decides *which* goals to hand out (it depends
on this change and on the work-cycle engine), the Discord answer bridge, and descendant accounting
for the fleet's sub-agent badges. Each is named so a later reader can tell *scheduled* from
*forgotten*.

## Capabilities

### New Capabilities

- `agent-goal-record`: an agent started by the framework carries a goal declared at the moment of the
  act — its text, its kind, who asked for it, and when — readable while the agent runs and surviving
  a restart of whatever started it, because the agent survives one too; an agent the framework did
  not start has no goal and is reported as having none rather than as having a trivial one.
- `agent-goal-closure`: a goal is closed by evidence the framework can check itself, reusing the work
  unit's verdict-against-the-tree rather than defining completion a second time; a goal whose
  fulfilment has no checkable artifact is declared unverifiable and stays open for a person; a closed
  agent releases its seat and leaves its record behind.
- `agent-session-rotation`: when remaining context falls below a declared bound, the framework writes
  a handoff and rotates the session in place through the pseudo-terminal it owns — one process, one
  label, one tile, a new session id — and refuses to attempt it where it does not own the terminal or
  cannot establish that the agent is between turns.

### Modified Capabilities

- `context-window-metrics`: its **Requirement: Context window size constant** mandates
  `CONTEXT_WINDOW_SIZE = 200_000` as a named constant. Measured 2026-08-19, the harness reports
  `context_window_size` per model in the payload it hands the statusline, and an agent started with
  the framework's own default argv reported `Ctx: 4% (36801/1000k)` — a **1M** window, which the
  constant renders as **18 %**. So the constant is not merely inflexible, it is currently wrong by a
  measured factor of five, and every utilisation percentage computed from it is wrong with it. The requirement becomes: the window size
  is read from what the runtime reports for the model in use, and a size it cannot obtain is reported
  as unknown rather than substituted.

## Impact

- `lib/set_orch/fleet/` — the goal record is written by the component that starts an agent, because
  that is the only moment the relation exists, and **durably**, because that component does not
  currently outlive the agents it starts. Layer 1 stays abstract: it knows about a goal, a kind
  and a verdict, not about what any project's goals are.
- **A new dependency in one direction only**: this change reads the work unit's verdict; the engine
  must not learn about goals. `set_workcycle` already imports from `set_orch` and never the reverse.
- `lib/set_orch/api/` — the goal and its closure join the fleet inventory payload. No existing route
  changes shape.
- `web/src/` — the agent tile carries the goal, its kind and its closure state. The tile already
  exists; this adds fields to it.
- **The context reading needs a carrier, and which one is measured before it is chosen.** The
  statusline payload is proven to contain the numbers, but it is delivered on render, which is a
  proxy for "the agent is running". A hook fired at a defined moment would be the better trigger if
  one carries the same figures. The first task group settles this; nothing is designed around either
  answer first.
- **A rotation is destructive if it lands wrong**, so it is bounded like every other write path in
  this repository: it happens only to a process the framework started and holds, and never to a tree.
- `context-window-metrics`' consumers — the monitor that computes utilisation and the set-web change
  list that displays it — change with its constant.
- Not touched: `ralph-session-continuation`, which continues a loop across **separate processes** by
  `--resume`. That is a different mechanism for a different situation, and this change must not grow
  into a second copy of it.
