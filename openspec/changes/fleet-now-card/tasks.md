## 0. Agreements and the dependency — nothing in section 2 is built before 0.1 is on the record

- [x] 0.1 Propose the `owner-queue` / `owner-queue-act` shape (spec `owner-queue-contract`) on the bus to the project that will publish it; ask whether it already keeps an equivalent ranked list and under which field names; amend the spec to the agreed names and record the answer in design.md Open Questions [REQ: the-publishers-shape-is-agreed-before-the-adapter-is-built]
- [x] 0.2 In `fleet-waiting-on-you`, mark its section 3 (header chip and panel) and its "no answering in the panel" non-goal as superseded by this change, with a pointer here; leave its aggregator, API and sources as they are [REQ: the-merged-order-is-the-publishers-rank-then-the-framework-sources-by-age]
- [x] 0.3 Build `fleet-waiting-on-you` sections 1–2 (aggregator and API) first, or confirm they exist, since this change reads them [REQ: the-merged-order-is-the-publishers-rank-then-the-framework-sources-by-age]

## 1. Card state and merge (Layer 1, `lib/set_orch/fleet/now.py`, new, domain-free)

- [x] 1.1 State store at the user's local data dir (`now/state.json`): snoozes, focus projects, cue history, closed count, keyed by opaque item ids and registry project names; atomic write; no item text [REQ: the-card-persists-no-item-content]
- [x] 1.2 Merge: owner-queue items in rank order, then framework items not covered by any `references`, oldest first; snoozed items excluded until their time [REQ: the-merged-order-is-the-publishers-rank-then-the-framework-sources-by-age]
- [x] 1.3 Focus filter: at most three focus projects; non-focus items held back unless no focus item exists or the deadline is within the configured window; counts of held-back items kept [REQ: the-day-has-up-to-three-focus-projects]
- [x] 1.4 Breakpoint detector from the fleet's last human input per agent: project-of-last-input change, the focus-threshold and the off-plan nudge, cue backoff after N unacted cues [REQ: cues-fire-at-breakpoints-rarely-and-back-off]
- [x] 1.5 Unit tests for 1.1–1.4, each proved to fail with its implementation stashed [REQ: the-merged-order-is-the-publishers-rank-then-the-framework-sources-by-age]

## 2. The owner-queue adapter (Layer 1) — after 0.1

- [x] 2.1 Read `owner-queue` through the status-contract reader; publisher chosen from local config, ambiguity reported when two declare it and none is named; not-declared distinct from empty [REQ: owner-queue-is-an-ordinary-declared-read-command]
- [x] 2.2 Parse the item shape; required fields enforced, optional fields passed through as display-only; `complete` and `rankedAt` carried as markers [REQ: the-owner-queue-item-shape]
- [x] 2.3 Write path: call `owner-queue-act` with `{ id, action, option?, text?, reasons?, until? }`; carry `{ outcome }`; refusal carries the project's reason; no write command declared → actions limited and stated [REQ: owner-queue-act-receives-the-cards-actions]
- [x] 2.4 Tests for 2.1–2.3 with a fake declared endpoint, including a refusal and a missing write command [REQ: owner-queue-act-receives-the-cards-actions]

## 3. The API (`lib/set_orch/api/now.py`, a separate router — `api/fleet.py` was being edited in parallel)

- [x] 3.1 `GET /api/fleet/now` → current item, following count, held-back count, unmeasured sources with reasons, partial/stale markers, closed count, cue decision, wind-down flag [REQ: the-now-window-shows-one-item-never-a-list]
- [x] 3.2 `POST /api/fleet/now/act` → answer, done, delegate (with reasons), later (snooze held locally), park-idea, resume-note, wind-down-handoff; relayed agent questions answered through the question relay's existing route [REQ: a-question-is-answered-with-one-tap]
- [x] 3.3 Log lines carry item id, action kind and outcome status only; a test asserts no title, option or answer text reaches a log record or the state file [REQ: the-card-persists-no-item-content]

## 4. The `/now` page (`web/src/pages/Now.tsx`, route in `web/src/App.tsx`)

- [x] 4.1 One card: project, sentence, why, estimate; "N more" without titles; empty state with closed count; large type sized for a small window [REQ: the-now-window-shows-one-item-never-a-list]
- [x] 4.2 Gap markers on the card: unmeasured sources, partial queue, ranking age, "cues slowed", "no ranked queue published" [REQ: a-gap-is-shown-where-the-reader-is-standing]
- [x] 4.3 Option buttons; delivered → outcome feedback that closes after 10 s; failure feedback stays until dismissed; undelivered keeps the item [REQ: a-question-is-answered-with-one-tap]
- [x] 4.4 Go there (fleet tile focus / status row / bus entry / publisher link) and dictate via `VoiceInput`, typed field when voice is unavailable [REQ: go-there-and-dictate]
- [x] 4.5 Done / Later (interval picker) / Delegate; keeping a delegable item asks for one or two reasons, never more [REQ: done-later-and-delegate]
- [x] 4.6 Feedback text from the outcome; no streaks, points or loss framing anywhere on the page [REQ: feedback-names-the-outcome-not-the-person]
- [x] 4.7 Sound: Web Audio tones varied per cue; first-open click to enable, "sound off" until then [REQ: cues-fire-at-breakpoints-rarely-and-back-off]
- [x] 4.8 Focus picker (max three, swap prompt on a fourth), resume note on removal and its display on return [REQ: the-day-has-up-to-three-focus-projects]
- [x] 4.9 Wind-down mode after the configured hour: tomorrow's first card, hand-off of delegable items, park with resume notes, one neutral line; the queue stays reachable [REQ: wind-down-after-a-configured-hour]
- [x] 4.10 Idea-parking control; only the parked count is shown [REQ: ideas-are-parked-not-started]
- [x] 4.11 Component tests for 4.1–4.10 [REQ: the-now-window-shows-one-item-never-a-list]

## 4b. Added after first use (2026-10-30)

- [x] 4.12 Tag strip: one tag per project with its count, click to switch off/on, persisted across days, hidden count under the card and in the empty state (`lib/set_orch/fleet/now.py` apply_mute/groups/set_muted, `POST /api/fleet/now/groups`, `TagStrip` in Now.tsx); tests proved to fail without the code [REQ: the-owner-can-switch-projects-off-on-a-tag-strip]
- [x] 4.14 Not needed with a one-line reason on every item; Go there only where there is a place to go (no status-page fallback for ranked items) [REQ: done-later-and-delegate]
- [x] 4.13 Labelled header counts, tooltips on every control, a ? legend overlay (`fd98a50a`) [REQ: the-card-explains-itself]

## 5. Launcher (`bin/set-now`)

- [x] 5.1 Open `/now` as a compact app window; where `wmctrl` exists set it above other windows; log what it did and what it could not do [REQ: the-now-window-shows-one-item-never-a-list]

## 6. Verification

- [x] 6.1 `pnpm build` and `tsc -b` in `web/` [REQ: the-now-window-shows-one-item-never-a-list]
- [ ] 6.2 Regression check against a baseline actually run (the `regression-baseline` skill) [REQ: the-merged-order-is-the-publishers-rank-then-the-framework-sources-by-age]
- [ ] 6.3 Visual check in the browser of the `/now` window at its launcher size: one card, the gap markers, an answer round-trip with feedback, Go there landing on the agent tile, wind-down mode; if the browser cannot be reached this task stays open [REQ: the-now-window-shows-one-item-never-a-list]
- [ ] 6.3a Looked at so far (2026-10-29, headless Chrome at 440x320 and 460x440, both themes, every write blocked): one card, the gap marker, options and actions visible, wind-down view. Found and fixed: the answer bar was below the fold at the launcher size (`dfdeb81d`). NOT yet looked at: an answer round-trip with its feedback, Go there landing on an agent tile, the dictate control (absent in the headless run — voice availability unverified), the sound cue. The Chrome extension was not connected, so 6.3 stays open. [REQ: the-now-window-shows-one-item-never-a-list]
- [ ] 0.4 The publisher emits `references` only to its own internal sources, so the de-duplication against agent questions (AC-4) never fires on real data and those questions follow the ranked items a second time; the publisher should reference `{source: "agent-questions", id: "agent:<session id>"}` when an item covers a live agent's question [REQ: the-merged-order-is-the-publishers-rank-then-the-framework-sources-by-age]
  - Progress 2026-10-30: the publisher now reads `waiting-on-you` and may reference its ids (publisher-side commit), but a dry run gave 0 references because every agent question had `title: null`; set-core now titles an agent question with the agent's last words (`0786b37b`, `55cd3de8`, live: 15 of 17 titled). Next dry run: 1 framework reference, matching a live id. Open: whether the ranker links more of them over a few real runs — measure before ticking.
- [ ] 6.4 One week of use, then read the cue log: cues acted on vs ignored, and the measured answer latency for card items vs before; record both with the command that produced them [REQ: cues-fire-at-breakpoints-rarely-and-back-off]

## Acceptance Criteria (from spec scenarios)

### fleet-now-card
- [x] AC-1: WHEN the merged queue holds five items THEN the first item is shown and "four more" without titles [REQ: the-now-window-shows-one-item-never-a-list, scenario: five-items-are-open]
- [x] AC-2: WHEN every measured source is empty and none is unmeasured THEN the page says nothing is waiting and shows the closed count [REQ: the-now-window-shows-one-item-never-a-list, scenario: nothing-is-open]
- [x] AC-3: WHEN the owner-queue command fails and the other sources are empty THEN the card names the unreadable source and does not say nothing is waiting [REQ: a-gap-is-shown-where-the-reader-is-standing, scenario: the-owner-queue-cannot-be-read]
- [x] AC-4: WHEN an owner-queue item references an agent question also listed by the framework THEN it is shown once, in the owner queue's position [REQ: the-merged-order-is-the-publishers-rank-then-the-framework-sources-by-age, scenario: the-owner-queue-references-an-agent-question]
- [x] AC-5: WHEN no project declares `owner-queue` THEN framework items are shown oldest first and the card says no ranked queue is published [REQ: the-merged-order-is-the-publishers-rank-then-the-framework-sources-by-age, scenario: no-owner-queue-is-published]
- [x] AC-6: WHEN an option is tapped THEN the write command receives the id and option, and on success the outcome is shown and the next item follows [REQ: a-question-is-answered-with-one-tap, scenario: an-option-is-chosen]
- [x] AC-7: WHEN the write command refuses with a reason THEN the reason is shown and the item stays [REQ: a-question-is-answered-with-one-tap, scenario: the-write-is-refused]
- [ ] AC-8 (unit-level only: the card opens `/?agent=<session id>` and the fleet consumes the parameter; landing on the tile is checked in 6.3): WHEN Go there is chosen on an agent item THEN the fleet opens with that agent's tile focused [REQ: go-there-and-dictate, scenario: an-agent-item]
- [x] AC-9: WHEN no speech service is configured THEN dictate is absent and a typed field is offered [REQ: go-there-and-dictate, scenario: voice-input-is-not-available]
- [x] AC-10: WHEN Done is chosen on a delegable item THEN one or two reasons are asked for and sent with the action [REQ: done-later-and-delegate, scenario: keeping-a-delegable-item]
- [x] AC-11: WHEN Later is chosen for two hours THEN the item returns after two hours and nothing is sent [REQ: done-later-and-delegate, scenario: later]
- [x] AC-12: WHEN an answer is delivered with an outcome THEN the outcome and the closed count are shown and close after 10 s [REQ: feedback-names-the-outcome-not-the-person, scenario: a-delivered-answer]
- [x] AC-13: WHEN input moves from project A to B and the first item changed since the last cue THEN one cue plays [REQ: cues-fire-at-breakpoints-rarely-and-back-off, scenario: leaving-a-project]
- [x] AC-14: WHEN work in a focus project exceeds the focus threshold THEN no cue plays [REQ: cues-fire-at-breakpoints-rarely-and-back-off, scenario: a-long-block-in-a-focus-project]
- [x] AC-15: WHEN three consecutive cues get no action THEN the interval doubles and "cues slowed" is shown [REQ: cues-fire-at-breakpoints-rarely-and-back-off, scenario: ignored-cues]
- [x] AC-16: WHEN a fourth focus project is added THEN the card asks which one to swap out [REQ: the-day-has-up-to-three-focus-projects, scenario: a-fourth-project]
- [x] AC-17: WHEN a project leaves focus with a resume note THEN the note shows on its first card when it is next in focus [REQ: the-day-has-up-to-three-focus-projects, scenario: resume-note]
- [x] AC-18: WHEN the configured hour passes THEN wind-down actions are offered and the queue stays reachable [REQ: wind-down-after-a-configured-hour, scenario: the-hour-passes]
- [x] AC-19: WHEN an idea is parked THEN it is sent to the publisher and the parked count rises by one [REQ: ideas-are-parked-not-started, scenario: parking-an-idea]
- [x] AC-20: WHEN an action is delivered THEN its log line names id, action kind and outcome status, and no item text [REQ: the-card-persists-no-item-content, scenario: logging-an-action]

### owner-queue-contract
- [x] AC-21: WHEN a project declares `owner-queue` THEN the card reads it as the owner queue [REQ: owner-queue-is-an-ordinary-declared-read-command, scenario: a-project-declares-the-command]
- [x] AC-22: WHEN two projects declare it and none is named in config THEN neither is shown and the ambiguity is stated [REQ: owner-queue-is-an-ordinary-declared-read-command, scenario: two-projects-declare-it]
- [x] AC-23: WHEN an item carries only the required fields THEN Done, Not needed and Later are offered, Go there only with a link, and nothing else [REQ: the-owner-queue-item-shape, scenario: a-minimal-item]
- [x] AC-24: WHEN an item carries three options THEN three option buttons are shown [REQ: the-owner-queue-item-shape, scenario: options-are-present]
- [x] AC-25: WHEN `rankedAt` is older than the configured age THEN the ranking's age is shown next to the item [REQ: incomplete-and-stale-answers-are-marked-not-hidden, scenario: a-stale-ranking]
- [x] AC-26: WHEN the write command prints an outcome THEN the card shows it [REQ: owner-queue-act-receives-the-cards-actions, scenario: an-answer-with-an-outcome]
- [x] AC-27: WHEN `owner-queue` is declared without `owner-queue-act` THEN only Go there and Later are offered and the card says no actions are accepted [REQ: owner-queue-act-receives-the-cards-actions, scenario: no-write-command-is-declared]
- [ ] AC-28: WHEN the publisher already uses different field names THEN the spec is amended to them before the adapter is written [REQ: the-publishers-shape-is-agreed-before-the-adapter-is-built, scenario: the-publisher-proposes-different-names]
- [x] AC-29: WHEN a project with two items is switched off THEN the other project's item shows, two are counted as hidden, and the tag keeps its count [REQ: the-owner-can-switch-projects-off-on-a-tag-strip, scenario: switching-a-project-off]
- [x] AC-30: WHEN every remaining item is switched off THEN the empty state names the hidden count [REQ: the-owner-can-switch-projects-off-on-a-tag-strip, scenario: everything-left-is-switched-off]
- [x] AC-31: WHEN the help control is opened THEN the legend names every part and the card stays [REQ: the-card-explains-itself, scenario: opening-the-legend]
- [x] AC-32: WHEN the owner chooses Not needed with a reason THEN Done is sent with that text and the item closes [REQ: done-later-and-delegate, scenario: not-needed]
