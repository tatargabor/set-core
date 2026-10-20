## Context

The fleet screen (`web/src/pages/Fleet.tsx`, project column
`web/src/components/FleetProjectColumn.tsx`, rows built by `web/src/lib/fleetColumnView.ts`)
renders projects as flat rows. The payload behind it (`GET /api/fleet/agents`,
`lib/set_orch/api/fleet.py:552`) already carries the per-agent sub-list (`FleetProject.agents`
with `pid`, `name`, `session_id`, `state`, `declared`, `purpose`) — so the tree is primarily a
rendering change plus one new resolved field.

Prior art this change builds on:

- **The shell phase machine** — `lib/loop/prompt.sh:31 detect_next_change_action()` derives
  `none | ff | apply | done` from the artifact tree (tasks.md missing → artifacts phase;
  unchecked numbered tasks → apply; archived → done). Never lifted into Python.
- **Python task counting** — `lib/set_orch/fleet/purpose.py:read_progress()` counts numbered
  `- [ ]` tasks (acceptance criteria deliberately excluded) and returns
  `Progress{done,total,partial,measured,fraction}`. The same module's `read_purposes()` binds
  work-cycle records to pids/sessions and its docstring states the governing refusal: gaps are
  reported, never filled.
- **Declared stage orders** — the project-status contract's `stageOrder` role
  (`lib/set_orch/project_status.py` `LIST_ROLES`/`_stage_list`, TS mirror
  `web/src/components/statusShape.tsx`) and its grouping/rendering
  (`web/src/lib/stageGroups.ts`, `web/src/components/StatusTable.tsx` `StageStrip`). Static
  order, empty stages drawn, strays marked, malformed → no role. Validated 2026-08-29 against a
  live producer.
- **Agent selection** — clicking an agent tile calls `writeView(project, {enlarged: pid})`
  (`web/src/lib/fleetViewState.ts`); per-project focus is restored on return.

Constraints: the dashboard is a product, not a debug view (compact, legible; compacting must
never hide a failure); nothing derived from a consumer project is persisted; producers get zero
obligation from the default path (a project mid-implementation must not be asked to change its
process); the framework stays domain-free.

## Goals / Non-Goals

**Goals:**

- One agent sub-row per live agent under its project row, clickable to focus the agent.
- A compact per-agent stage strip: flow shape visible, done/running/pending distinct, gaps
  and strays marked, never rendered as calm.
- Stage resolution with a zero-declaration default (OpenSpec tree) and a declared override
  (existing contract), joined per agent session.
- Additive payload change; existing consumers unaffected.

**Non-Goals:**

- Changing `stageOrder`'s contract, validation, or the project-status table strip.
- Recorded (non-live) sessions as sub-rows; docking/tab/terminal layout changes.
- Any persistence of derived stage data; any per-stage colours/icons config surface (the
  field-role vocabulary stays closed).
- Orchestrated changes' `current_step` vocabulary — that is orchestration state, not the
  OpenSpec artifact lifecycle, and the two are not unified here.

## Decisions

### D1 — Derive the default flow in a new Python module beside `purpose.py`

New `lib/set_orch/fleet/stage.py` (name at implementation discretion): a Python lift of
`detect_next_change_action`'s artifact logic extended to the five-stage axis
`proposal → design → apply → verify → archive`, reusing `read_progress` for counts rather than
re-implementing the numbered-task regex.

- *Why not extend the shell function*: the fleet backend is Python; shelling out to
  `prompt.sh` from an API request couples a GUI read path to a loop-interactive script and its
  stdio conventions.
- *Why not store the phase when a change is written*: derivation-on-read needs zero producer
  cooperation and cannot go stale the way a cached phase would; it also honours the
  no-persistence constraint for free. Cost: a small filesystem read per agent per poll (5 s),
  bounded by one directory listing plus one regex count — the same cost class
  `read_purposes` already pays.

Mapping (falls back to the first matching rule):

| evidence | stage |
|---|---|
| change found only under `openspec/changes/archive/` | `archive` |
| `tasks.md` present, all tasks checked | `verify` |
| `tasks.md` present, ≥1 unchecked | `apply` |
| proposal present, no `tasks.md`, design/specs artifacts present or absent | `design` |
| proposal only, no design artifacts, no `tasks.md` | `proposal` |

A change directory with no recognizable artifact resolves to no position (gap), not to
`proposal` — a directory is not evidence of a proposal.

### D2 — Session→change join: work-cycle record first, session-record inference second

Resolution order per agent: (1) a work-cycle record binding the agent's session/pid to a change
(`read_purposes`), (2) the change name inferred from the session's own record (the existing
scraper at `lib/set_orch/api/sessions.py:52`). If both fail → explicit gap.

- *Why not join on "the project's single active change"*: two agents of one project on two
  changes must not be collapsed; the spec forbids computing one agent's stage from another's
  change. When exactly one active change exists and inference fails, the gap is still reported —
  a likely guess is a fabricated value wearing evidence's clothes.
- The inference scraper is heuristic by nature; its misses are exactly the gaps the refusal
  rule expects to surface, and they are visible instead of wrong.

### D3 — Declared override reads the existing contract answer, adds no new surface

If the project's project-status answer declares `stageOrder` on a stage field, that declared
order is the flow for the project's agents and the producer's stage values position them. The
validation and all-or-nothing semantics are the already-specified ones
(`_stage_list` → `None` on malformed); this change adds a *reader*, not a second vocabulary.
Malformed → fall back to the derived flow, per spec.

- *Why not a new fleet-specific declaration*: two places to declare the same flow would drift;
  the contract answer already reaches the backend (`/api/{p}/project-status`) and is the
  sanctioned path for producer-owned per-item state.
- Precedence is per project and total: declared replaces derived for that project's agents.
  Mixing half a declared flow with half a derived one is the partial-order false value the
  stage-order work explicitly rejected.

### D4 — Strip rendering reuses `stageGroups` semantics, new compact component

The sub-row strip is a new small component in the fleet column that consumes the same grouping
shape (`stageGroups`-style: seeded declared stages, strays kept and flagged) fed from the
payload's flow + position, rather than re-rendering `StageStrip` (a table strip, wrong density
and interactivity for a sub-row). Colour mapping: completed → one hue, current → another,
pending → neutral, gap → the marked-empty style, strays → the amber/⚑ treatment already
established. One colour per meaning across both strips wherever the palette allows.

- *Why not reuse `StageStrip` directly*: it renders row counts for a table; the sub-row renders
  one agent's position. Forcing one component would make it two-dimensional (mode flag,
  count-vs-position) to save a small second renderer — the same strip-versus-columns trade the
  stage-order change already settled by choosing the plainer rendering.

### D5 — Tree rows live in the column view model

`buildColumnView` grows agent sub-rows under each project row (respecting the active
filter/mode), and `FleetProjectColumn` renders them; click wires to the existing
`writeView(project, {enlarged: pid})`. Default expand state follows the row's selection: the
selected project's agents are visible; others collapse. No new fetch — the data is already in
the polled payload.

- *Why selection-follows expansion over independent expand buttons*: the primary use is the
  shortcut (click the agent, not the pane title); per-project expand state in
  `fleetViewState` is the fallback if the collapsed default proves wrong in use.
- Sub-rows are skipped for projects with zero live agents — a tree of empty project nodes is
  noise, and the row already shows agent counts.

## Risks / Trade-offs

- [Per-poll derivation cost across a large fleet] → one listing + one regex per agent's change,
  same class as existing purpose reads; measure with the fleet payload's existing timing before
  optimizing (cache only if measured, keyed on change-dir mtime).
- [Session→change inference misses make many agents look gapped] → gaps render distinctly and
  the join order puts the reliable work-cycle record first; a gapped agent is visible truth, and
  improving inference later is additive.
- [Five-second poll recomputes stages constantly] → derivation is pure and cheap; no state to
  invalidate because nothing is stored.
- [Consumer project names or stage values leaking into logs] → the resolver logs shapes and
  counts, never values or project identifiers, matching the established logging rule.
- [Strip colour collisions with existing fleet status dots] → the fleet screen already assigns
  meaning to colours (working/waiting/attention); pick the three stage hues from what remains
  unclaimed and verify against the live screen, per the UI look rule.

## Migration Plan

Additive end to end: new resolver module, new payload field, new sub-rows. No data migration, no
producer action, no flag needed — a consumer reading the old payload shape ignores the new field,
and the column without sub-rows is today's screen. Rollback is reverting the commits.

## Open Questions

- Whether recorded-but-not-live roster sessions should later appear as dimmed sub-rows
  (deferred; out of scope here, revisited after live use).
- Whether the derived flow should one day itself be overridable by a project-local declaration
  outside the status contract (deferred; the contract override covers the known need — the
  producer's custom flow).
