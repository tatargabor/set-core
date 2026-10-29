## Context

**What was measured, and how** (2026-10-29, one owner's machine; the numbers motivate the shape and
are not targets):

| fact | how it was measured |
|---|---|
| 272 structured agent questions in 14 days, median answer 3 min, 24 over an hour | `AskUserQuestion` tool calls and their results in the native session transcripts, timestamp difference |
| 36 project switches/day (median), 7 projects/day, median visit 6.3 min, 46 % of visits one prompt | human prompts in the native transcripts, ordered by time across all projects; a visit = consecutive prompts in one project less than 30 min apart |
| 14 of the 15 visits over an hour went to one project | same series |
| starting or redirecting work outnumbers continuing it about 2:1; finishing words in 3 % of dictations | a hand classification of 41 dictations, stratified by project; a word search over 259 |
| ten separate pull surfaces hold owner items; the bus owner view returned 0 against 338 prose-addressed actions | direct inspection of each; `sac owner --json`; a text count in one room |
| an agent ranked twelve projects' next moves, with sources, in about four minutes | a one-off prototype run against the owner's real projects |

The fleet already has most of the parts: per-agent attention classes and last human input
(`fleet/state.py`, the roster), the question relay (`fleet/question_relay.py`), the jump to an agent
tile, the dashboard's voice input (`VoiceInput.tsx`, used by `FleetInstruct.tsx`), and the
status-contract reader with separate read and write namespaces. `fleet-waiting-on-you` plans the
aggregator (`fleet/waiting.py`) and `GET /api/fleet/waiting-on-you`; one of its 33 tasks is done.

**Evidence from outside the repository that decides details** (grades: S strong, M moderate,
W weak):

- Externalising the plan at the point of performance, one concrete next step (CBT for adult ADHD —
  Safren 2010, Solanto 2010; meta-analysis Young 2016: S for the package, W for the component alone).
- Steep delay discounting (Jackson & MacKillop 2016, S) → feedback must be immediate.
- Informational feedback raises intrinsic motivation; controlling praise and expected rewards lower
  it (Deci, Koestner & Ryan 1999, S) → name the outcome, never grade the person; no streaks.
- Attention to a repeated alert habituates in 1–3 exposures; varied alerts resist it (Anderson,
  Vance et al. 2015/2017, M); interruptions at breakpoints cost less than mid-task (Iqbal & Bailey
  2008, M).
- Consider-the-opposite reduces bias (Lord, Lepper & Preston 1984, M); two counter-reasons
  debias, ten backfire (Sanna, Schwarz & Stocker 2002, W/M) → ask for at most two.
- Attention residue after leaving an unfinished task (Leroy 2009, W/M); a ready-to-resume note
  reduces it (Leroy & Glomb 2018, W) → resume notes on parking.
- Chronic short sleep degrades executive function while self-rated sleepiness barely moves
  (Van Dongen 2003, S/M) → wind-down mode states one neutral fact; it does not coach.
- No study tests cue cadence, gamification or hyperfocus exit in adults with ADHD → every such
  parameter is configuration, and the card logs whether a cue was acted on so the setting can be
  tuned from the owner's own data.

## Goals / Non-Goals

**Goals:**
- The owner sees the one thing to do next without opening anything, and can do the common case —
  answer a question — without leaving the card.
- set-core stays domain-free: it shows, routes and remembers *shape*; the publishing project owns
  every word of item content and all ranking.
- Every gap is visible on the card (unreadable source, partial queue, stale ranking, cues slowed).

**Non-Goals:**
- Ranking in set-core. The publisher ranks; the card trusts its order.
- Replacing any existing list. Owner inboxes, follow-up lists and the fleet's chips stay; the card
  reads through them.
- A phone or chat channel. The owner said such a channel goes unopened; the card is the surface.
- Enforcing behaviour. Nothing locks, blocks or hides the queue — not at night, not for a fourth
  project.

## Decisions

### D1. A route of the existing web app, opened as an app window

`/now` in `web/` is opened as a compact browser app window and kept on top by the window manager. A
small launcher (`bin/set-now`) opens it with a fixed size and, where `wmctrl` exists, sets the
above-others flag.

*Alternatives:* a native widget (GTK, Electron, Tauri) — a second toolchain for one card; a
notification daemon — notifications are transient and the card is a standing state; a chat channel
— measured to go unopened.

### D2. Ranking is the publisher's, done by an agent with deterministic inputs

The user asked for an agentic ranking explicitly ("lehet, hogy a döntés az jó, hogyha agentik"),
and the prototype supports it: an agent read twelve projects and produced a ranked list whose top
items were all things no list held as "waiting" (a near deadline found in a plan file, a send blocked
by an empty field). A deterministic formula over deadline/age would have missed them. Deterministic
measurements are still the agent's inputs and are carried on each item (`deadline`, `unblocks`,
`estimateMinutes`) so the card can show *why*. A reviewing second agent, if any, is the publisher's
business.

### D3. Merge: publisher order first, framework items de-duplicated by reference

Owner-queue items keep their rank. Framework items (agent questions, run state, bus-to-owner) that
an owner-queue item `references` are dropped; the rest follow, oldest first. Without a publisher the
card degrades to the framework sources alone, and says so.

### D4. Actions go through the contract's write command, not a bus message

`owner-queue-act` returns synchronously with an outcome or a refusal reason, under write-failure
rules the contract already has. A bus message has no delivery semantics the card could show as
"delivered" — the defect class of reporting a 200 as an arrival. Agent questions held by the relay
are answered through the relay's existing route.

### D5. Answering in the card — reverses `fleet-waiting-on-you`'s non-goal

That change said answers belong where the question lives. The measurement says otherwise: a question
in front of the owner is answered in minutes, and going to the project to answer is the switch that
costs a visit and leaves residue. *Go there* stays for anything that needs the project.

### D6. Card state is local and keyed by opaque ids

`~/.local/share/set-core/now/state.json` holds snoozes, focus projects, cue history and counts, keyed
by item ids and registry project names. Owner-written text (resume notes, parked ideas) goes to the
publisher via `owner-queue-act`; only without a publisher is a resume note kept locally.

### D7. Cues: breakpoints from last human input, Web Audio, backoff

A breakpoint is the project of the owner's most recent input changing (the fleet already records
the last human input per agent). Tones are synthesised with Web Audio, with pitch and contour varied
between cues. The browser requires one gesture before audio plays; the card asks for one click on
first open and shows "sound off" until it has it. After N unacted cues the interval doubles and the
card says "cues slowed".

### D8. Delegation asks for at most two reasons

Keeping a delegable item asks for one or two reasons, never a longer list (D-evidence above). The
reasons go to the publisher with the action, so the publisher can learn which work the owner keeps.

## Risks / Trade-offs

- [The publisher's ranking is wrong] → the card shows `why` and `rankedAt`; Later and the reasons
  sent with Done/Delegate give the publisher a correction signal.
- [The card becomes the eleventh ignored surface] → it is push (always on top, cues at breakpoints)
  rather than pull; the cue log shows whether it is acted on, which is the measurement that decides.
- [Cue fatigue] → breakpoint-only, varied tones, automatic backoff shown on the card.
- [Item content leaks into logs] → a test asserts that no title, option or answer reaches a log
  record or the state file.
- [Depends on `fleet-waiting-on-you`] → the card works with the owner queue alone; framework sources
  appear when that aggregator lands.
- [Two publishers] → local configuration names one; ambiguity is shown, not guessed.

## Migration Plan

None. A new route, a new endpoint pair, a new launcher; `fleet-waiting-on-you`'s chip and panel
tasks are marked superseded in that change.

## Open Questions

- The publisher's actual field names — proposed in `owner-queue-contract`, to be agreed on the bus
  before the adapter is built.
- Whether "delegate" targets a named colleague or an unattended agent is the publisher's choice; the
  card sends only `delegate`.
