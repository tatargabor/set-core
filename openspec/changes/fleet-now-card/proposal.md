## Why

The owner runs many projects in parallel through agents, and work stalls on the owner without
anybody noticing — not because the owner decides slowly, but because what waits on them is out
of sight. Stated by the user on 2026-10-29 (dictated): *"mindegyiket valahogy kicsit elfelejtem,
és nem haladnak"*, and what they asked for: *"egy olyan egyszerű felület kellene, ami … folyamatosan
nyitva van … és mutatja hogy mit kéne csinálnom. Melyik projektben mi akadt meg."* — always on
top, because *"Discordot megint nem nyitom meg, elfelejtem."*

Measured the same day, on this machine (method in design.md, Context):

- **Visible questions are answered fast; invisible ones are not answered at all.** Over 14 days
  agents asked the owner 272 structured questions; the **median answer came in 3 minutes**. Over
  the same period, items written as prose — into lists, files and bus broadcasts — sat for days
  to weeks.
- **There is no shortage of lists.** At least ten places already record what waits on the owner
  (project-side owner inboxes and follow-up lists, a copilot work queue, a coordinator's
  operations watch, the fleet's PM mode, relay chip, awaiting counts and wave boards, a daily
  chat brief). Every one is a *pull* surface. The fleet's own "waiting on owner" bus view
  returned **0** while one room held 338 owner-addressed actions written as prose.
- **Attention moves fast and narrowly.** A median of 36 project switches and 7 projects a day,
  a median visit of 6.3 minutes, and 14 of the 15 visits longer than an hour went to a single
  project. Work that decays is work that is *almost done*.
- The previous attempt at this — `fleet-waiting-on-you`, asked for on 2026-10-19 — stands at 1 of
  33 tasks, which is the pattern itself: one more pull surface, waiting to be opened.

## What Changes

- **A "Now" card**: a small window the owner keeps always on top, served by the fleet, that shows
  **one item at a time** — project, one imperative sentence, why now, an estimate — and never a
  list. Behind it: a count of what follows and of any source that could not be read.
- **One-tap answers.** An item that is a question carries its answer options as buttons, the
  shape the owner already answers in minutes. **Go there** jumps to the agent or status row it
  came from; **dictate** answers by voice, reusing the dashboard's existing voice input.
- **Done / Later / Delegate.** *Delegate to a colleague* is the default question on every
  delegable card; keeping the item asks for one or two reasons (the owner's own design:
  *"meg kelljen indokolnom, hogy miért ne adjuk le"*).
- **Outcome feedback instead of praise or streaks**: after an action the card says what the
  action caused (*"answered → the agent is working on it"*), and a day's closed count. No
  streaks, no loss framing.
- **Interruption at breakpoints only.** A rare, varied sound cue when the owner *leaves* a
  project, never in the middle of a long working block; one nudge after a configurable time in
  a project that is not on today's plan.
- **Day shape**: a morning pick of up to three focus projects with the rest visibly parked
  (each with a resume note); a wind-down mode after a configurable evening hour that turns the
  card toward "tomorrow's first card" and handing work to unattended agents.
- **Idea parking**: one control that records a new idea as parked instead of starting work on it;
  the card shows only the parked count.
- **A new source: the owner queue.** A project the owner designates (their personal copilot)
  publishes a **ranked** cross-project queue through a declared status-contract read command,
  `owner-queue`, and accepts the card's actions through a declared write command. Ranking —
  including *proactive* items (what is worth moving even when nothing is waiting) — is done on
  the project side by an agent, with deterministic inputs (deadline, what it unblocks, nearness to
  done). set-core stays domain-free and persists no item content.
- The card also shows the sources `fleet-waiting-on-you` already plans (agent questions,
  framework run state, bus entries addressed to `owner`), through that change's aggregator and API.
  **This change supersedes that change's header chip and panel (its D5) and reverses its
  "no answering in the panel" non-goal**; its aggregator, API and sources stand.

## Capabilities

### New Capabilities
- `fleet-now-card`: the Now window — one item at a time, its actions (answer, go there, dictate,
  done, later, delegate), cues and their cadence, outcome feedback, the day shape (focus
  projects, parking, wind-down), idea parking, and the persistence boundary on what it shows.
- `owner-queue-contract`: the declared read command `owner-queue` and write command
  `owner-queue-act` a project publishes so the card can show a ranked, cross-project queue and
  hand actions back — the item shape, ranking inputs carried for display, completeness and
  staleness markers.

### Modified Capabilities
- None. `fleet-waiting-on-you` is not yet archived, so its superseded parts are recorded in that
  change rather than as a delta here. The project-status contract already separates read and
  write commands; `owner-queue` and `owner-queue-act` are ordinary declared commands under it.

## Impact

- **Layer 1 (core, domain-free):** `lib/set_orch/fleet/now.py` (new) — merges the owner-queue
  answer with the `fleet-waiting-on-you` aggregator's items, holds the card state that is not
  item content (snoozes, the day's focus projects, the closed count) keyed by opaque item ids;
  `lib/set_orch/api/fleet.py` — `GET /api/fleet/now`, `POST /api/fleet/now/act`.
- **Depends on** `fleet-waiting-on-you` tasks for `fleet/waiting.py` and its API (sources 1, 2, 4).
- **Web:** a new route `/now` (`web/src/pages/Now.tsx`) built to be opened as a separate
  always-on-top app window; reuses `VoiceInput` and the fleet's existing jump to an agent tile.
- **Project side (not in this repo):** the designated project implements `owner-queue` and
  `owner-queue-act`, ranks, and owns all item content. Its shape is proposed here and agreed with
  that project over the bus before the adapter is built.
- **Persistence:** item titles, options and reasons are project content — displayed at request
  time, never logged, cached to disk, or written into any artifact.
