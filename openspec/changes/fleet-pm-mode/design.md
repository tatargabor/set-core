## Context

The fleet screen (`web/src/pages/Fleet.tsx`, `lib/set_orch/fleet/`) lists every discovered agent
and measures each one's state from its session log (`lib/set_orch/fleet/state.py`). The measurement
is deliberately structural: an outstanding `tool_use` with no `tool_result` means the agent is
mid-turn, everything else is `quiet`, and nothing is ever called *idle*.

That module's own header names the limit this change works inside: **the log separates working from
not-working, and cannot separate "stopped at a prompt" from "finished its turn"** — both look like a
turn that ended. Today the gap is filled by `_apply_declared_wait`, which upgrades a quiet agent to
`waiting` only when the runtime's session record declares it. Measured `GET /api/fleet/agents` on
2026-08-20: **18 agents, 0 waiting, 17 quiet, 1 unknown**. On 2026-08-19 it was 1 of 22. A queue
built on that source alone is empty in practice.

Three further measurements shape the design, all taken on this machine:

| measurement | value | where it lands |
|---|---|---|
| agents with a framework-held terminal | 16 of 18 | full-screen presentation is possible for most, not all |
| quiet agents by who spoke last | 12 agent · 3 user · 2 nothing | the 3 are turns dropped on the floor, invisible today |
| `AskUserQuestion` call → result gap | 8m13s · 9m32s · 1m43s | the outstanding call is visible while the person thinks |

The last row is the finding that reorders the work: a question tool sitting outstanding is a
*structurally certain* blockage on a person, and `read_state` returns `working` for it.

## Goals / Non-Goals

**Goals:**
- One presented agent at a time, chosen for the reader, advancing only when they have dealt with it.
- A structural floor under the model's judgment, so the most certain blockages need no opinion.
- One model invocation per cycle for the whole fleet.
- A freeze the reader can trust while typing, and a preemption rule that still respects freshness.
- Nothing derived from a consumer session is written down.

**Non-Goals:**
- Notification outside the fleet screen (no desktop notification, no bus message, no email).
- Any new way of answering an agent. The existing terminal and instruct box are what exist.
- Queueing work that has no agent on it (`awaiting`, measured at 3 with 46 projects unmeasured).
- Consuming the work-cycle engine's `NEEDS_INPUT` envelope. It is a natural third feed and it has
  its own change (`work-cycle-question-outbound`); wiring it here would couple two unfinished things.

## Decisions

### D1 — Two sources of truth, ranked: a structural floor, a model layer above it

```
   session logs
        │
        ├── structural pass (code) ──▶ blocked-on-person   ── certain, free, unarguable
        │        outstanding AskUserQuestion / ExitPlanMode
        │
        └── candidate filter ────────▶ one model call ─────▶ asked / finished / stopped
                 quiet · log moved · not already decided
```

**Why not model-only**, which is what the request literally asked for: the structural cases are
free and certain, and running them through a model makes the most reliable signal in the system
depend on the least reliable one. **Why not code-only:** deciding whether prose is a question is
reading a verdict out of prose, a defect class this repository has paid for repeatedly.

The ranking is one-directional and specified: a model verdict may **add** items, never remove a
structurally measured one. Disagreement is recorded rather than resolved.

*Alternative rejected:* a keyword/`?` heuristic as a cheap middle layer. It is a proxy for a
decision, and its failure direction is silent — a question phrased as a statement ("I'll need the
API key before I can continue") is exactly the case the mode exists for.

### D2 — The declared question-tool list is a list, and the design assumes it is incomplete

`AskUserQuestion` and `ExitPlanMode` are the two measured today. A permission prompt is **not**
included: from the log it is indistinguishable from a slow `Bash`, so including it by elapsed time
would queue every long-running command. The list is declared in one place and named in the spec as
a list precisely so that adding to it is a one-line change and *guessing* at it is not possible.

### D3 — One stateless invocation per cycle; the queue's memory is code

The request was "one Sonnet, not one per agent". Implemented as a single `claude -p`-style
invocation per cycle carrying every candidate, rather than a long-lived session.

A resumed session accumulating a day of fleet tails would compact, and a compacted context keeps
confidence while losing precision — the queue would re-present items it had already shown, and be
sure it had not. Everything the queue must remember (presented, answered, deferred, dismissed,
history) is ordinary state in the framework, re-derivable and testable.

*Cost accepted:* the invocation re-sends each candidate's tail every cycle it changed. The candidate
filter is what keeps that bounded — quiet only, log-changed only, not-already-decided only.

### D4 — "Dealt with" is measured as the agent resuming

Refuted by measurement rather than reasoned about: a new `user` entry is not proof. An interrupt
writes `[Request interrupted by user]` as a user message, so `Esc` would advance the queue — the
exact behaviour the freeze exists to prevent.

The test is that the agent **resumed**: a new assistant utterance or a new outstanding call after
the blockage point. It is late by one turn-start, and that is the right trade: the alternative is a
maintained list of the runtime's synthetic markers, which is a second copy of somebody else's
format and drifts the day they add one.

### D5 — Typing is the guard; the countdown is a courtesy

```
 typed within the window (default 20s) ──▶ no switch, no countdown, no prompt
 silent + a fresher blockage exists    ──▶ countdown (default 5s), ANY key cancels
 silent + nothing fresher              ──▶ frozen, as requested
```

Two separate mechanisms deliberately. If the countdown were the guard, the reader would have to
watch for it — and a mode that demands vigilance to avoid losing a half-typed answer is a mode that
gets turned off. **Any** key cancels rather than a specific one, because typing *is* the evidence of
engagement and nobody should have to remember which key rescues them.

*Corrected by the pre-apply review, 2026-08-20 — this said the signal needed no new plumbing, and
that was an assumption stated as a fact.* `term.onData` at `web/src/components/FleetTerminal.tsx:283`
is a single choke point for every keystroke, so the signal exists — but the component's props are
`{ label, onClose, full, onToggleFull, onFocusChange }` and none of them surfaces it. It is a small
addition, and the reason to record it is that "already present" is exactly the phrasing that makes
somebody skip the task.

**And `onData` does not cover the whole answer path.** An answer typed into the instruct box never
reaches the terminal, so the guard would miss it — and for an agent with no framework-held terminal
(2 of 18 measured) the instruct box is the only way to answer at all. Both inputs count as typing.

### D6 — Freshest-first, with demotion paying for the starvation

Ordering is by how recently the agent became blocked, newest first — inverting the usual fairness
rule. The justification is the prompt cache: an agent answered while its cache is warm resumes from
it, one answered much later re-reads its context. The framework asserts no particular TTL; it
follows the direction.

Starvation is the obvious cost. Two things pay it: nothing ever leaves the queue except by being
dealt with, and the count of what is queued is visible in the always-on frame. A third, from the
same reasoning: an item the reader sat silently in front of is **demoted** when it returns, because
their silence is evidence they will not answer it now — without that, the freeze rule would
re-present the same item first on every cycle.

### D7 — Nothing is persisted, so the queue is rebuilt rather than restored

The confidentiality boundary in `CLAUDE.md` is persistence, not display. The mode may show a
consumer's session text and may send it to the judging model; it may not write it down. So the
queue holds identities, classes and timestamps, and a service restart empties it until the next
cycle. Storing the queue on disk would be the convenient design and is ruled out here rather than
discovered later.

The user has explicitly accepted that the judging model reads consumer session content
("ez az én PM-em", 2026-08-20). That acceptance covers the *reading*; it does not relax the
persistence rule, which also protects against a diagnostic dump leaving the machine.

### D8 — Where the pieces live

| piece | home | layer |
|---|---|---|
| question-tool classification, resumed signal | `lib/set_orch/fleet/state.py` | core, existing |
| candidate filter + judgment pass | new module under `lib/set_orch/fleet/` | core |
| queue, ordering, preemption, history | new module under `lib/set_orch/fleet/` | core |
| PM endpoints | `lib/set_orch/api/fleet.py` | core |
| model role `pm` → `sonnet` | `lib/set_orch/model_config.py` | core |
| toggle, frame, counts, back/forward | `web/src/` | web |

Nothing here is project-type-specific, so nothing belongs in `modules/`. Nothing is deployed to a
consumer by `set-project init`.

### D9 — This lands in core, not as a plugin, and the seams are where a plugin boundary would go

Considered and deliberately deferred on 2026-08-20. Measured first, because the answer turned on
what already exists rather than on preference:

- set-core already has **three** `entry_points` extension groups — `set_core.api_routes`
  (wired at `lib/set_orch/api/__init__.py:73`), `set_tools.project_types`, and
  `set_orch.deferred_work`. Enumerating every installed distribution's entry points found
  **zero** packages registering into any of them; even the built-in web module loads through the
  `modules/` path rather than an entry point.
- The dashboard is one Vite bundle mounted as static files (`web/package.json` build =
  `tsc -b && vite build`; `lib/set_orch/server.py:155`). A plugin can add API routes today. It
  cannot add a screen, and this feature is mostly screen. `KNOWN_PANEL_KINDS` is a registry, but a
  compile-time one.

So a fourth extension group would extend a mechanism with no users, and the feature would split
across two repositories while its shape is still moving — the most expensive moment to do that.

What this change does instead is place the seams where the boundary would fall, so extraction later
is a move rather than a rewrite: the cycle is not woven into the server, the model is already a
declared role, the endpoints live under their own router, and the presentation is assembled from the pieces the
fleet screen already owns rather than woven through it.

*Narrowed by the pre-apply review, 2026-08-20.* This first named `KNOWN_PANEL_KINDS` as the seam.
Measured: that registry holds exactly one kind (`PANEL_AGENT`), and `resolvePanels` serves the
remembered **dock arrangement** — while PM mode is a page-level mode, not a docked panel, and
`FleetTerminal`'s `full` prop is a per-tile enlarge rather than a page state. The registry is the
right seam for a docked view and the wrong one for this; claiming it would have sent the
implementation somewhere the code does not go. Extraction proves a seam;
designing one in the abstract does not.

*Separate question, deliberately not merged into this one:* shipping set-core's `.claude/` surface
(22 `set:` commands, 12 generated `opsx:` commands, 13 skills, 3 agents, 11 hooks, 1 MCP server) as
a Claude Code plugin instead of copying files into consumer trees. That is about the deploy engine,
not about fleet features, and it has a much larger prize — it would dissolve the write-path problem
class rather than guard it.

## Risks / Trade-offs

- **The base specs for the two modified capabilities are not archived yet.** `agent-fleet-state` and
  `agent-fleet-surface` live in the unarchived `fleet-view` change (228/232 tasks). → The deltas
  here are written against those files; archiving `fleet-view` first is the ordering that makes them
  land cleanly, and the modified requirement was copied whole from it rather than paraphrased.
- **The model classifies "asked me something" wrongly in either direction.** A false positive wastes
  a screenful of attention; a false negative leaves an agent stuck all day. → The fail direction is
  chosen deliberately: bias toward queueing, because the reader can dismiss an item in one keystroke
  and cannot discover one that was never queued. The dismissal count is reported, so the bias is
  measurable rather than assumed.
- **A judgment pass that silently returns nothing renders as a calm fleet.** → An unmeasured
  judgment is a distinct state on the frame, and previous verdicts stand rather than being cleared.
- **Cost grows with fleet size and churn.** 18 agents today, no bound in the design. → The candidate
  filter is the control; the cycle period and a maximum candidates-per-pass are declared values, and
  a pass that would exceed them reports what it did not cover rather than truncating silently.
- **The freeze can strand the reader.** Frozen on a hard question, everything else piles up. → The
  count is always visible, back/forward is available, and dismissal is one action.
- **A screen that renders is not a screen that works.** The whole change is a layout that hides
  things by design. → A browser check of the real screen is a task, not an afterthought, and it
  stays open if the browser cannot be reached.

## Migration Plan

No data migration; the mode is off by default and holds no persisted state. The state-layer fix
ships first and independently — it corrects a false value on today's screen whether or not PM mode
is ever turned on. Rollback is turning the toggle off; removing the feature removes no state.

## Open Questions

- **DECIDED 2026-08-20 (user): option (a).** The confidentiality requirement was narrowed to the
  framework's own logs, records and caches, and the runtime's session journal is a named, bounded
  exception — invoking a model writes the prompt there by construction, so forbidding it would
  forbid the feature. What it adds is a second machine-local copy of content that already exists in
  the judged agents' own logs. The exception is not widened: no framework log, no cache, no queue
  record, no committed artifact, nothing that leaves the machine. `run_claude_logged` is kept, with
  its event and verdict plumbing.
- **What period should a cycle run at?** Not decided. The candidate filter makes a short period
  cheap in the common case, but the ceiling should be a declared value chosen against a measured
  cost, not guessed here.
- **Should a dismissed item ever come back?** Currently it leaves the queue and is counted. If a
  reader dismisses something and the agent stays blocked for hours, nothing brings it back.
- **Do the 3 "user spoke last, agent never replied" agents belong in this queue at all?** They are
  not blocked on the reader — the reader already spoke. They are dropped work. Queued as
  "stopped for another reason" for now; they may deserve their own class.
