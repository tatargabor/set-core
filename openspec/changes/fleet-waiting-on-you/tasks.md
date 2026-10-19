## 0. Agreements — sources 3 and 4 are not built before these are on the record

- [ ] 0.1 Propose the `questions` command shape (design D3) to the consumer on the bus; ask whether their coordinator already produces this list and in what shape; record the answer in `docs/integration/consumer-integration.md` and rewrite D3 to the agreed shape [REQ: project-questions-are-read-from-a-projects-declared-command]
- [ ] 0.2 Propose the `owner` addressee and a machine view (design D4) to `set-agent-comm`; record what they decide, including what makes an entry open [REQ: bus-entries-addressed-to-the-owner-are-read-through-the-buss-own-machine-view]

## 1. Aggregator and the two measured sources (Layer 1, `lib/set_orch/fleet/waiting.py`)

- [ ] 1.1 `SourceResult` and the aggregator: total of measured sources only, unmeasured count and reasons; an adapter that raises becomes unmeasured with a WARNING naming the source [REQ: the-owners-queue-has-four-sources-and-each-is-measured-on-its-own]
- [ ] 1.2 Agent-question adapter from `ATTENTION_WAITING_CLASSES` and the relay's waiting record, de-duplicated by session with the relay record winning (design D2) [REQ: agent-questions-come-from-the-attention-classes-and-the-question-relay]
- [ ] 1.3 Run-state adapter over `awaiting_for` per project, keeping each kind, excluding `unverifiable`, counting `source_missing` projects as unmeasured [REQ: framework-run-state-contributes-its-existing-awaiting-kinds]
- [ ] 1.4 Unit tests for 1.1–1.3, each proved to fail with its implementation stashed [REQ: the-owners-queue-has-four-sources-and-each-is-measured-on-its-own]

## 2. The API (`lib/set_orch/api/fleet.py`)

- [ ] 2.1 `GET /api/fleet/waiting-on-you` returning all four sources (3 and 4 as unmeasured with reason "not agreed yet" until section 4 lands) [REQ: the-queue-is-one-api-answer-that-other-surfaces-can-read]
- [ ] 2.2 Test that no log record carries an item title or text while items are present [REQ: the-queue-is-one-api-answer-that-other-surfaces-can-read]

## 3. The header control and panel (`web/src/components/FleetWaitingOnYou.tsx`, `web/src/pages/Fleet.tsx`)

- [ ] 3.1 Chip beside the relay chip with the total and an unmeasured marker, both visible closed [REQ: the-header-shows-the-total-and-the-panel-floats]
- [ ] 3.2 Floating panel: absolute positioning, closes on its control and Escape, no auto-close; oldest first, grouped by project, blocked-release marker, unmeasured sources named with their reason [REQ: the-header-shows-the-total-and-the-panel-floats]
- [ ] 3.3 Links: agent item → `goTo` the agent; project item → its status row; bus item → the room entry [REQ: the-header-shows-the-total-and-the-panel-floats]
- [ ] 3.4 Component tests for 3.1–3.3 [REQ: the-header-shows-the-total-and-the-panel-floats]

## 4. The two agreed sources — only after section 0

- [ ] 4.1 Project-question adapter through the status-contract reader for the agreed command; not-declared distinct from zero open; contract failure classes carried; `complete: false` carried as a marker [REQ: project-questions-are-read-from-a-projects-declared-command]
- [ ] 4.2 Bus adapter through the agreed machine view; no text parsing, no direct store reads; unavailable view reported as unmeasured [REQ: bus-entries-addressed-to-the-owner-are-read-through-the-buss-own-machine-view]
- [ ] 4.3 Tests for 4.1–4.2, including a broadcast that mentions the owner in text and is not listed [REQ: bus-entries-addressed-to-the-owner-are-read-through-the-buss-own-machine-view]
- [ ] 4.4 Measure against the live consumer: the panel's project-question count against the consumer's own report of items waiting on the owner; record both with the command [REQ: project-questions-are-read-from-a-projects-declared-command]

## 5. Verification

- [ ] 5.1 `pnpm build` in `web/` and `tsc -b` [REQ: the-header-shows-the-total-and-the-panel-floats]
- [ ] 5.2 Regression check against a baseline actually run (the `regression-baseline` skill) [REQ: the-owners-queue-has-four-sources-and-each-is-measured-on-its-own]
- [ ] 5.3 Visual check in the browser: the chip with its count and marker, the panel opening without moving anything, each link landing where it says; if the browser cannot be reached this task stays open [REQ: the-header-shows-the-total-and-the-panel-floats]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN the bus cannot be read and the other sources hold 4 items THEN the total is 4 and one source is reported unmeasured with its reason [REQ: the-owners-queue-has-four-sources-and-each-is-measured-on-its-own, scenario: an-unreadable-source-is-not-a-zero]
- [ ] AC-2: WHEN two sources hold items THEN each count is reported separately alongside the total [REQ: the-owners-queue-has-four-sources-and-each-is-measured-on-its-own, scenario: sources-are-not-merged-into-one-count]
- [ ] AC-3: WHEN a question is held by the relay and the agent also reads as waiting THEN exactly one item is listed [REQ: agent-questions-come-from-the-attention-classes-and-the-question-relay, scenario: a-relayed-question-is-listed-once]
- [ ] AC-4: WHEN an agent has waited 12 minutes THEN its item names agent, project and the wait [REQ: agent-questions-come-from-the-attention-classes-and-the-question-relay, scenario: a-waiting-agent-is-listed-with-its-wait]
- [ ] AC-5: WHEN a project's run state holds one stalled change THEN one `stalled` item is listed [REQ: framework-run-state-contributes-its-existing-awaiting-kinds, scenario: a-stalled-change-is-listed-with-its-kind]
- [ ] AC-6: WHEN one project declares no command and another answers with no items THEN the first is not declared and the second zero open [REQ: project-questions-are-read-from-a-projects-declared-command, scenario: not-declared-is-not-nothing-open]
- [ ] AC-7: WHEN an item names the release it blocks THEN the listed item carries it [REQ: project-questions-are-read-from-a-projects-declared-command, scenario: a-blocked-release-is-carried]
- [ ] AC-8: WHEN a broadcast mentions the owner only in its text THEN it is not listed [REQ: bus-entries-addressed-to-the-owner-are-read-through-the-buss-own-machine-view, scenario: prose-addressing-is-not-counted]
- [ ] AC-9: WHEN the bus view is unavailable THEN the bus source is unmeasured with the reason [REQ: bus-entries-addressed-to-the-owner-are-read-through-the-buss-own-machine-view, scenario: the-bus-view-is-unavailable]
- [ ] AC-10: WHEN the endpoint is called THEN all four sources are named with count and measured flag [REQ: the-queue-is-one-api-answer-that-other-surfaces-can-read, scenario: the-answer-carries-every-source]
- [ ] AC-11: WHEN the queue is built with items THEN no log line contains an item's title or text [REQ: the-queue-is-one-api-answer-that-other-surfaces-can-read, scenario: logs-carry-no-item-content]
- [ ] AC-12: WHEN a source is unmeasured and the panel closed THEN the chip shows the marker [REQ: the-header-shows-the-total-and-the-panel-floats, scenario: unmeasured-is-visible-while-closed]
- [ ] AC-13: WHEN the panel opens THEN nothing beneath it moves or resizes [REQ: the-header-shows-the-total-and-the-panel-floats, scenario: opening-the-panel-moves-nothing]
- [ ] AC-14: WHEN an agent item is followed THEN that agent's project is selected and the agent enlarged [REQ: the-header-shows-the-total-and-the-panel-floats, scenario: an-agent-item-leads-to-the-agent]
