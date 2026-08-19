## Context

`fleet-view` can say what an agent is *doing*, read from its own session log. It cannot say what the
agent was started *for*, so it cannot say whether the work is finished — and a finished agent and a
stalled one render identically. The goal was supposed to arrive with the work-cycle engine
(`fleet-view/tasks.md:15`) and did not: progress landed there as `AC-29`, the goal is absent from
every spec in that change.

Three constraints shape everything below.

- **The framework owns a pseudo-terminal for the agents it starts, and nothing else.** An agent
  opened by hand in an editor cannot be written into — the kernel forbids injecting into a terminal
  the sender does not own. `fleet-view` measured this for input and it does not move here.
- **Layer 1 stays abstract.** A goal, a kind and a verdict are framework concepts; what any project's
  goals *are* is not.
- **Nothing derived from an agent's session is persisted.** A goal record that carries a closing
  summary written by the agent would cross that line at exactly the moment it looks most useful.

All measurements referenced below are in `measurements.md`, taken 2026-08-19 unless dated otherwise.

## Goals / Non-Goals

**Goals:**

- An agent the framework starts has a goal, recorded at the moment of the act.
- A goal closes on evidence the framework checks, and closing stops the agent.
- An agent low on context is rotated in place — one process, one label, one tile — with a written
  handoff as the carrier.
- The existing 200 000-token constant stops being the divisor of every utilisation figure.

**Non-Goals:**

- Deciding which goals to hand out, or in what waves. That is the dispatcher, and it depends on this.
- Any goal accounting for sub-agents. Measured: a spawned child writes **no transcript of its own**
  and the parent records only the act (a `tool_use` named `Agent` with an `agentId`); `isSidechain`
  was 0 across 98 transcripts and 1 positive probe. Accounting for them is real work, not a detail.
- Replacing the harness's own compaction. See D4.
- Answering a stopped agent's question through any channel. That is the Discord bridge, and the
  `deferred-work-connector` already declares that filling its directory is the caller's business.

## Decisions

### D1 — The goal record lives with the component that starts the agent, keyed by label

The record is written by the owner that creates the process, because that is the only moment the
relation exists. Measured for the sibling relation (`fleet-view` task 2.5): **0 of 23** live agents
had an agent ancestor, and a framework-started agent's parent is a plain owner process — so no walk
over processes, logs or registries recovers who wanted what. `requested_by` had to be recorded during
the act; a goal is the same shape and is recorded the same way.

*Keyed by label, not by pid* — because D4 keeps the process and rotates the session, while a crash
and restart would keep neither. `fleet-view` task 7.5 already keys the open terminal by label for the
same reason.

**Read before designed, and the reading changed this decision twice** (2026-08-19):

- **`OwnedAgent.requested_by` already exists** (`lib/set_orch/fleet/owner.py:121`), recorded in the
  act of starting, for the same measured reason given above. The goal is a field beside it, not a new
  subsystem — inventing a parallel record here would be the failure this repository names.
- ⚠ **But the owner persists nothing, and that inverts the decision.** `AgentOwner` holds its agents
  in an in-memory dict; the only write in `ownerd.py` is the `health` command printing JSON. And
  `recover(owner, unit, session_id, cwd, label, resume_argv)` (`ownerd.py:378`) **takes no
  requester**. Meanwhile `scopes.py` deliberately starts each agent in its own transient scope *so
  that it outlives the service*. So the agent survives a restart the record does not — and a goal
  stored the way `requested_by` is stored would disappear while its agent kept working.

  Hence the requirement added to `agent-goal-record`: the goal is written durably at the moment of
  the act and survives the owner, and a recovered agent whose goal cannot be restored is reported as
  **unrecoverable** rather than as having none. Those are different claims about the same screen, and
  collapsing them is the false-absence class.

### D7 — The goal is not `Purpose`, and the boundary between them is stated so neither grows into the other

`lib/set_orch/fleet/purpose.py` already answers *what an agent is working towards* — change, unit,
group, kind, verdict, progress — by reading the work-cycle engine's on-disk records, never what an
agent says, and deliberately without importing the engine.

They answer different questions and must not merge:

| | `Purpose` (exists) | goal (this change) |
|---|---|---|
| question | what work record exists for this agent | why this agent was started |
| source | the engine's records, read | declared by the caller, written at the act |
| exists for | agents running an engine unit | every framework-started agent, engine or not |
| when absent | no engine record — reported as nothing | only for agents the framework did not start |

The practical consequence is that `agent-goal-closure` does not need a new evidence reader:
`Purpose` already carries the `verdict` and a `progress.measured` flag, and already refuses to derive
progress from turn counts. D2's "reuse the verdict" therefore names an implementation, not an
aspiration.

**Alternatives considered.** *In the agent's own session log* — impossible: it is the agent's
artifact, and reading it back would make the goal a claim rather than a record. *On the messaging
bus* — the bus is an optional dependency and an agent that enrolled no seat is still an agent. *In
the project's tree* — a write into a consumer tree, guarded for good reason, and meaningless for an
agent with no project.

### D2 — Closure reuses the work unit's verdict; the dependency points one way only

Where a goal names work the engine ran, closure is the engine's verdict **diffed against the tree**
(`work-unit-engine` AC-29 and the verdict/tree diff). This change adds no second definition of
"finished".

The direction is a decision, not an accident: this capability imports from the engine and the engine
learns nothing about goals. `set_workcycle` already imports from `set_orch` and never the reverse; a
goal concept leaking into the engine would make the engine undeletable.

**Where there is no unit**, the goal declares itself unverifiable at declaration time and stays open
for a person. Deciding *at closing time* that a goal was unverifiable would turn every failed check
into a reason to close — the fail direction that costs.

### D3 — The context reading needs a carrier, and the carrier is measured before it is chosen

**Proven:** the runtime hands a statusline command a `context_window` object with
`context_window_size` (per model), `used_percentage` and `remaining_percentage`, plus `session_id`
and `transcript_path`. **Proven:** `--settings <file-or-json>` accepts a settings file from anywhere,
so the framework hands a framework-started agent its own statusline carrier **without writing into
the project's tree** — the cheapest way to satisfy this repository's write guards is not to be a
write path at all.

**Settled 2026-08-19, and the answer is negative:** no hook carries the figures. Nine were
registered and eight fired — `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`,
`SubagentStop`, `SessionEnd` — and `context_window` appears in the statusline dump alone. So the
statusline is the carrier, chosen because it is the only one, not because it is the best shape.

Its cadence was measured rather than hoped: **5 renders in 56 s, gaps 3.0–20.8 s**, event-driven
rather than timed. That is adequate for a reason worth stating, because "fast enough" would be luck:
a rotation can only happen between turns (D5), so the reading's granularity matches the act it gates.

⚠ **And the very first render carries a size with NO usage** — `used_percentage: null`,
`total_input_tokens: 0` — so a naive division reports **0 %, meaning plenty of room**, for a reading
that does not exist. This is the reassuring direction of the false-value class, and it is the
concrete reason `unknown` below must be a value rather than a number.

`PreCompact` never fired in the probe and is **unmeasured**. It would be the better trigger in
principle — it fires exactly when the runtime is about to compact, which is the event a threshold is
a proxy for — but every hook that *was* measured lacks the figures, so it stays a hypothesis.

**The delivery was measured end to end (task 1.3), including the part that could have been
destructive.** An agent started with `--settings <framework-owned>` in a tree carrying its own
`.claude/settings.json` produced real statusline renders, and the tree came out **byte-identical with
no new file**. The merge is **per-key**: the project's `UserPromptSubmit` hook still fired (lists are
additive), while a colliding `statusLine` went to the framework 2 renders to 0 (scalars override).
The first half is what matters — a consumer's gate chain hangs off hooks, and a framework that
replaced them would disable the thing an entire safety track exists to protect. The second half is
acceptable and is **stated rather than discovered**: for an agent the framework starts, the
framework's status line replaces the project's.

**Fail direction, decided now regardless of the carrier:** a reading the framework cannot obtain is
`unknown`, and `unknown` never triggers a rotation. Rotating on a reading nobody has would clear a
conversation for no established reason; declining merely postpones.

### D4 — Rotation is `/clear` on the owned pty, and the honest justification is weaker than it looks

**Measured:** `/clear` rotates the session id and the transcript *inside the same process* — pid
1701204 and its `/proc/<pid>/stat` starttime token unchanged across it, one transcript before and two
after. So the process, the pty, the label and the tile all survive.

**Re-measured on the real configuration (task 1.4)** rather than on the probe's cheap model:
`["claude", "--dangerously-skip-permissions"]` verbatim from `ownerd.py:65`, the transcript reporting
`claude-opus-5`. Same pid, same starttime token, one transcript before and two after. The systemd
scope was not exercised — it changes the cgroup, not the tty or the session identity — and 5.3 runs
the real path.

That run also produced the sharpest evidence for the window-size defect this change corrects: the
agent's own status line read **`Ctx: 4% (36801/1000k)`**. Against the `200_000` constant the same
session renders as **18 %** — a measured 5× overstatement, in the direction that calls a session with
96 % of its context free nearly full.

**Alternatives considered, and why they lose:**

- *Start a successor and hand off to it.* Unnecessary after the measurement above, and it costs a
  second seat, a second label and a tile that moves — the very churn the surface exists to remove.
- *`--resume` / `--fork-session`.* Measured 2026-08-17 (`fleet-view` design §6.1): resuming a live
  session forks the running conversation into a second branch nothing reports. Refuted already.
- *Let the harness compact.* This is the real competitor and it must be stated plainly: measured, a
  single session file carries **11 compact summaries under one session id across 15 304 lines**. An
  agent whose context fills is *not* replaced and does *not* stop. So the justification for rotating
  is **not** "otherwise the agent dies" — that is false. It is that a compaction keeps confidence and
  loses precision, while a handoff is a written carrier that can be read back and disagreed with.
  A weaker claim, and the one that is true.

**Ordering is the safety of the whole mechanism:** the handoff is written and verified *by its trace
on disk* before any clear is sent, and a handoff that was not written cancels the rotation. A clear
that lands before its handoff exists destroys exactly what it was meant to carry.

### D5 — A rotation is verified by its trace, never by having sent the keystroke

`/clear` is a keystroke into a TUI, not an API call. It can be swallowed, land mid-turn, or stop
meaning what it means in a future version — and none of those raise an error. So a rotation counts as
having happened when the **session identity changed**: a new transcript alongside the old one under
the same process. This is the repository's standing rule (a subagent's "done" is not evidence) applied
to a keystroke.

It also decides the pre-condition: the agent must be established as *between turns* before the clear
is sent, and where turn state cannot be established, no clear is sent.

**Settled 2026-08-19.** Turn state comes from the framework's own `UserPromptSubmit` / `Stop` hooks,
installed through `--settings`. Measured over 32 samples across a 14 s tool-call turn and a
sub-second text-only turn: the pair read BUSY ×15 against a BUSY truth and IDLE ×7 against an IDLE
truth, with *no event yet* — honest unknown — as the only value on both sides, and only before the
session's first prompt. On the sub-second turn it read BUSY exactly during it.

**The obvious alternative is refuted, and refuted fail-open**, which is why it is recorded rather
than merely dropped: reading the transcript's last row overlaps on `last-prompt`, and on a text-only
turn the tail never becomes `assistant/tool_use` at all — it goes `attachment`, then `atis-latch`. So
*"busy iff the tail is a tool call"* says IDLE while the agent is answering, and the clear lands
mid-turn. The row types it does show are the runtime's internal bookkeeping; the tail correlated with
turn state without being about it. `pendingBackgroundAgentCount` was `None` throughout — it counts
background agents, not turns.

### D6 — Refusing a start without a goal changes an existing entry point

`fleet-view`'s `agent-fleet-terminal` starts an agent from the surface, and that path currently
supplies no goal. Once this change lands it must, which is a coordination item rather than a spec
conflict: that change is not archived, so its tasks can carry the addition. Named here so it is not
discovered during apply.

## Risks / Trade-offs

- **A TUI keystroke is a fragile interface** → the rotation is verified by the session-identity trace
  (D5), and a rotation that cannot be verified is reported as failed rather than assumed. A version
  change breaks the mechanism loudly instead of silently.
- **Rotation is destructive by construction** — it discards a live conversation → it is bounded to a
  process the framework started and holds, gated on a written handoff, and refused on unknown
  readings and unknown turn state. Three independent conditions, each failing closed.
- **An agent could thrash**, rotating every few minutes and never progressing → every rotation is
  recorded with its trigger and the count is readable beside the goal, so thrashing is visible rather
  than looking like steady work.
- **The statusline carrier only exists for framework-started agents** → a hand-opened agent's
  remaining context is `unknown`, which the spec already treats as inert. No behaviour depends on a
  figure that cannot exist.
- **`context-window-metrics` has downstream consumers** — the monitor's utilisation figure and the
  set-web change list → both change with it, and the unknown case gets a rendering rather than a
  zero. A blank or a `0%` would be the false-absence class landing on a screen.
- **The goal record is a place domain content can leak into** (a project's goal text names its
  domain; a closing summary would carry more) → the record holds the goal as declared and references
  its evidence by identity — a commit, a task marker, a verdict — and never copies a line of a
  transcript.

## Migration Plan

The three new capabilities are additive: an agent without a goal record is reported as having none,
which is the state of every agent that exists today, so nothing breaks on the day this lands.

`context-window-metrics` is the one behavioural change with existing consumers. Its constant is
removed and the divisor becomes the reported size; sessions with no reported size move from a wrong
percentage to `unknown`. Rollback is the constant's reinstatement, and it is worth noting that
rollback restores a figure that is currently wrong by a factor of five on this repository's own
sessions.

## Open Questions

- ~~Which carrier delivers the context reading~~ — **settled 2026-08-19 (D3): the statusline, because
  no hook carries the figures.** Remaining sub-question: whether `PreCompact`, which never fired in
  the probe, would be a better trigger than a threshold.
- ~~How turn state is established~~ — **settled 2026-08-19 (D5): the framework's own
  `UserPromptSubmit` / `Stop` pair.** The transcript-tail alternative is refuted and the refutation is
  in `measurements.md`, because it fails in the direction that clears a busy agent.
- **A hook payload is a persistence hazard.** `Stop` carries `last_assistant_message` verbatim, so a
  hook that logs what it receives writes conversation content to disk. The framework's hooks must
  record the event and never the payload — named here because it is a constraint on how D5 is built,
  not merely a caution.
- **What a goal's evidence looks like when the work was not run as work units.** The engine covers
  the ordinary case; a goal spanning several changes, or work done interactively, may need its own
  evidence shape rather than being declared unverifiable by default. Deliberately left open — this
  change is written to be updated once `work-cycle-engine-apply-first` finishes, and that is where
  the answer will be visible.
