## Why

The surface can say what an *orchestration run* is doing. It cannot say what an *agent* is doing —
and most agents on a developer's machine are not started by an orchestration run at all. They are
interactive sessions, opened by hand in an editor, one window each.

Measured on a live machine while writing this: the project list reported a project as `Stopped`,
last touched **24 days ago**, while **six live agent sessions** were working in it at that moment.
The answer was not wrong for what it measures — the orchestration state file genuinely had not
moved. It was wrong for what a reader takes it to mean. This is the *false absence* class from
`.claude/rules/evidence-discipline.md`: a screen announcing a calm it never measured.

The cost is paid in windows. Following N agents means N editor windows, switching between them to
see who is stuck, and typing or dictating into each one separately. Nothing on the screen says
*where the work is standing still* — which is the one question that decides what to do next.

Two capabilities that already exist make this cheap rather than speculative. Agent sessions write a
line-oriented log per session, which the framework already parses for its activity views. And an
agent messaging bus already establishes, per session, **who that agent is and how to reach it** —
so identity and delivery do not have to be invented here.

## What Changes

- **An agent inventory, assembled from three sources rather than one.** A live process (identified
  by its working directory, because an interactive session's command line names no project), the
  messaging bus registry (which binds a session id and a process id to an agent identity), and the
  project registry. Measured: the process-only and registry-only views of the same machine
  overlapped on **4 of 20** projects — either source alone hides projects where work is happening.
- **An agent's state read from its own log, not from a registry timestamp.** Whether a tool call is
  outstanding, and how long the log has been still. A registry's "last seen" is when a hook last
  ran, which is a proxy: measured, it reported an agent silent for 21 minutes whose log had been
  written to inside the same minute.
- **A two-panel surface**: projects as tiles on the left, each carrying how many agents it holds and
  in what state; the selected project's agents as tiles on the right, each with its declared focus,
  its current tool, a log excerpt, and its own input line.
- **Sending an instruction to an agent, with an honest delivery report.** A running session cannot
  be typed into from outside — the kernel forbids injecting into a terminal the sender does not own.
  The message therefore travels on the bus, and *when it arrives* depends on whether a waiter is
  running under that session. Measured on one machine: **4 of 12** live sessions would be woken
  immediately. A single "sent" confirmation would misreport the majority case, so the surface
  distinguishes: arrives now / arrives when the current turn ends / sits unread until someone types.
- **A project is one tile even when it has several worktrees.** A working directory identifies the
  project only through git: several checkouts of one repository share a common git directory.
  Measured on a live repository: **5 worktrees, one project**. Matching raw paths — which an earlier
  draft of this change did — scatters one project's agents across as many phantom projects as it has
  worktrees, and destroys the one question the left column answers. The agent tile carries its branch
  instead.
- **Where an agent came from, measured rather than declared.** An agent started by another agent is
  its process descendant, so walking the parent chain to the first agent process names the parent.
  This also yields a **role** — one that spawns is directing, one that was spawned is executing —
  and the role is measured, unlike the phase below.
- **What a project has wired in, shown as icons.** Which capabilities are connected — the messaging
  bus, spec tooling, orchestration, framework rules, MCP servers — is derived from files present in
  the project, with no project-type knowledge. A capability that could be wired in but is not is
  shown dimmed rather than omitted: absent and not-connected are different claims.
- **A phase is declared by the agent, never guessed by the framework.** Measured in a session that
  spent its whole length on spec work, the obvious signal — a slash command in the log — matched
  **zero** times. A guessed phase icon is wrong exactly when the situation is unusual, which is when
  the screen is being looked at. Where nothing is declared, no icon is shown. Deriving it from paths
  would also put domain knowledge into the abstract layer, which the architecture forbids.
- **Per-project view state**: which tile is enlarged, the grid density, and any unsent draft are
  remembered per project, so returning to a project returns to where the work was left.
- **Dictation into the same input**, reusing the voice component and key endpoint already shipped.
- **Nothing derived from an agent's log is persisted.** Read, shown, dropped — not to a cache, not
  to a log file, not into this repository. An agent log is the densest domain source there is.

- **Starting a session from the surface, with a full terminal attached.** The framework starts the
  agent process itself under a pseudo-terminal it owns, and the browser gets that terminal: typing
  into it *is* typing into the agent, without the messaging bus in between. This is the only path to
  direct input, and it exists **only for sessions the surface started** — the kernel boundary above
  does not move, so an agent someone opened in an editor is still reached over the bus. Whether such
  a session can be **adopted** by resuming it into a framework-owned terminal ~~is untested~~ **was
  measured on 2026-08-17 and the answer is no** (design §6.1): the resume succeeds, hands back the
  intact history and the same session id, and forks the running agent's conversation into a second
  branch nothing reports. So those tiles keep the bus input and say why, and the surface must
  additionally **refuse** to offer a resume on any session it can see is running.

Deliberately **out of scope for this change**: sub-agents (a session's own `Task` children).

## Capabilities

### New Capabilities

- `agent-fleet-inventory`: the framework assembles the set of live agents across all known
  projects from process state, the messaging registry and the project registry, never from one
  alone, and reports for each which sources knew about it.
- `agent-fleet-state`: an agent's activity is read from its own session log — outstanding tool
  call, time since the log last moved — and a state it cannot determine is reported as unknown,
  never as idle.
- `agent-fleet-instruct`: an instruction is delivered to an agent over the messaging bus, and the
  surface reports which of the three delivery outcomes actually occurred, taken from the bus's own
  answer rather than assumed.
- `agent-fleet-surface`: a two-panel screen showing projects and the selected project's agents,
  where every tile carries state, log excerpt and input, and no compaction hides an agent that is
  waiting. It is the application's **landing screen**, so its unfinished and empty states are part
  of the capability rather than edge cases: while discovery is still running the screen says it is
  looking, never that there is nothing.
- `agent-fleet-terminal`: the framework starts an agent under a pseudo-terminal it owns and streams
  that terminal to the browser in both directions, so a session started from the surface can be
  typed into directly. A session the framework did not start has no terminal offered — the tile says
  so rather than presenting a control that goes nowhere.

### Modified Capabilities

<!-- No spec delta is emitted here, and the reason is measured rather than assumed. The landing
     decision (design §5.1) moves what the application's root route renders: today it renders the
     projects overview, and it will render the fleet. The projects overview keeps every behaviour
     it has — its own route and a navigation entry — so no requirement of `projects-overview`
     changes.

     `unified-navigation` is the capability that would own the root route, and it does not: no
     requirement in it names `/` (checked: `grep -n 'root route|landing|index route|`/`'` over
     both spec files → no match). What it does describe is a sidebar of `/manager/*` and `/set/*`
     routes, which the application no longer has — they are legacy redirects in `App.tsx`. So that
     spec is stale against the shipped app in ways that predate this change, and rewriting it to
     reality is a separate piece of work, not a side effect of this one.

     Recorded rather than silently skipped: `unified-navigation` needs a retroactive correction
     pass. It is named in tasks.md so it does not evaporate. -->

## Impact

- `lib/set_orch/api/` — one new route module for the fleet inventory, per-agent log reads and the
  send path, plus a **bidirectional stream** for the terminal. No existing route is modified.
- `lib/set_orch/` — a new module for agent discovery and state derivation, and a second for
  **starting an agent under a pseudo-terminal the framework owns** and supervising its lifetime.
  Layer 1 stays abstract: it knows about processes, session logs, a pty and a bus, not about any
  project type.
- `web/src/App.tsx` — the root route renders the fleet; the projects overview keeps its own route
  and a navigation entry. This is the only edit to an existing file's behaviour.
- `web/src/pages/`, `web/src/components/` — the new screen, the agent tile and the terminal view.
  The voice input, WebSocket hook and design tokens are reused as they are. A terminal emulator
  component is a **new frontend dependency**; nothing in the app renders one today.
- **A process the framework starts outlives the request that started it**, so its lifetime is part
  of this change rather than an afterthought: what happens to that agent when the browser closes,
  when the service restarts, and how it is stopped. An agent left running with nothing pointing at
  it is the orphan class the fleet screen exists to make visible — this change must not create it.
- Optional dependency posture: the messaging bus may be absent. Then agents are still discovered
  and their state still read; only instruction is unavailable, and each tile says so rather than
  hiding its input line.

## Status

**Ready to apply as of 2026-08-17.** All eight decisions in `design.md` §5 are settled — four
answered by the user (§5.1, §5.2, §5.4, §5.8), four adopted from the measurement (§5.3, §5.5, §5.6,
§5.7), and each records which. `tasks.md` was deliberately absent until then, because a task list
written across an open decision is a decision made by default.

**Two of the answers went against the exploration's leaning, and they are what changed the shape of
this change**, so they are stated here rather than only in the design: the fleet becomes the
**landing screen**, and the **terminal is built now, in this change**, not in a follow-up. The
second roughly doubles the work and pulls one untested assumption onto the critical path — whether
an already-running session can be adopted into a framework-owned terminal by resuming it. That is
measured in the first task, before anything is designed around either answer, because a terminal
that only serves sessions the surface started is a different feature from one that serves the fleet.

**That measurement has since been made, and the user's response to it is part of the shape too**
*(2026-08-17)*. Resume-based adoption is refuted, which entitled the terminal work to shrink to
surface-started sessions. The user declined the shrink: the terminal keeps its planned size and the
search for another adoption route continues as its own measured task. So this change is no smaller
than it was, and the reason it is not is a decision rather than an oversight. The round also added
three requirements the plan did not have — a refusal to resume a live session, an agent that
registers nothing being an agent nonetheless, and waiting-for-a-person as a state of its own.

Second round of the exploration added the worktree, lineage, capability-icon, view-state and phase
items above, after a review of the first round's screens. One of them was a **correction**: the
first round showed a worktree as a separate project, which this change now forbids explicitly.
