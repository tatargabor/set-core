## Context

A wave board is a tracked job file, `docs/waveboard/<job>.json` (`set-wave-board/1`), in
the repository that runs the job; `set-wave-board sync` derives status from evidence and
the agent pushes the result to a read-only Artifact page. The fleet screen already knows
every project (registry ∪ messaging registry ∪ live agents, `discover_projects`) and is
the cross-project screen the user works from.

## Goals / Non-Goals

**Goals:** one glance at every project's boards from the fleet; one click into the
project, one click onto the board page; blocked work visible without opening anything.

**Non-Goals:** a second board renderer in the fleet (the page already exists), editing,
reading the page's live database, notifications.

## Decisions

**D1 — Read the tracked job file, not the page database.** The fleet server cannot read an
Artifact's database (only the agent's tool can), and the job file is the layer the board
itself calls most reliable. Trade-off: the agent's fast-lane `set` updates the job file at
once, but a status the page shows can be ahead of the file only if someone wrote the page
without the script — not a path the tooling offers. Each row shows when an item last
changed, so a stale file reads as stale.

**D2 — Projects from the registry and the messaging registry, no agent discovery.**
`discover_projects([], registered=…, messaging=…)` gives the same names the fleet shows,
without the cost of walking processes. A project known only through a live agent and not
registered anywhere is left out — measured: every board on this machine is in a registered
project.

**D3 — Summaries only.** The payload carries counts, the job, the board title and the page
URL; never an item title or note. Board titles are what the project chose to publish; item
content stays on the board page. Nothing is persisted (confidentiality is a persistence
boundary) and nothing is logged beyond counts and the file's job name.

**D4 — Unreadable is an entry.** A malformed file becomes `{unreadable: true, reason}`
rather than an omission — the "a gap is not a zero" rule; the chip counts unreadable
boards in the warning colour.

**D5 — A header chip + floating list, not a panel.** The fleet's panels are per project;
this view is across projects, so it belongs on the header strip with the other
cross-project facts. The list is `position: absolute` with a z-index, closes by its own
control, Escape and outside click, and never resizes the header (ui-quality: an overlay
never pushes). Blocked and unreadable counts sit on the closed chip (compacting never
hides a failure).

**D6 — Fetch on mount and every 60 s, independent of the agents poll.** Boards change on
the scale of minutes; reading ~50 directories is cheap but there is no reason to couple
it to the fleet's faster poll, and a slow read must not delay the agent list.

## Risks / Trade-offs

- [Job file lags the page] → each row shows the age of the last item update.
- [Many projects, slow disk] → a stat of `docs/waveboard` per project; files are small.
  The read is synchronous inside a threadpool route (FastAPI `def`), off the event loop.
- [A project's board title carries client wording] → it is displayed at runtime only and
  persisted nowhere, the same as every other project datum the fleet shows.
