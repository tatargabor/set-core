## 1. Liveness defects (Layer 1 core + service)

- [ ] 1.1 CORE — `MandateStore.end_missing` takes `unit_alive(unit) -> Optional[bool]`; a mandate whose unit is active or unmeasured is kept, with a log line; `api/fleet.py` `_settle_mandates` passes the systemd measurement. [REQ: a-mandate-is-ended-for-a-missing-agent-only-when-its-unit-is-measured-gone]
- [ ] 1.2 CORE — `MandateStore.reopen_desk(project, label, unit_alive)` re-opens the newest ended desk mandate under the label whose unit is active; `DeskResolver.resolve` calls it on `LabelHeld` before waiting for the seat. [REQ: a-running-desk-whose-mandate-was-ended-is-re-adopted-not-blocked]
- [ ] 1.3 CORE — The sweep keeps a desk whose seat asks an open engagement (`asking-open`); the close forecast agrees. [REQ: a-desk-waiting-on-its-own-request-is-not-swept]
- [ ] 1.4 TEST — Unit tests for 1.1-1.3, each proven by stash-and-rerun (fails without the fix). [REQ: a-mandate-is-ended-for-a-missing-agent-only-when-its-unit-is-measured-gone]

## 2. Stall measurement and the ladder (Layer 1 core)

- [ ] 2.1 CORE — `fleet/takeover.py`: `background_cpu_rate` from the scope cgroup minus the main process, sampled between rounds; unmeasured on the first sample or any read failure. [REQ: a-desk-is-stalled-only-when-nothing-shows-it-working]
- [ ] 2.2 CORE — `takeover.decide(engagement, desk_row, cpu_rate, now, bounds)` → `none | interrupt | replace | bound-reached`, with the reason; pure, every input passed in. [REQ: a-stalled-desk-is-interrupted-before-it-is-replaced]
- [ ] 2.3 CORE — Engagement record: `nudged_at`, `handovers`; `mark_nudged`, `mark_handover` (re-points desk fields, keeps `open`). [REQ: a-gone-or-still-stalled-desk-is-replaced-by-a-desk-that-takes-the-request-over]
- [ ] 2.4 CORE — Mandate record: `takeover` object; `render_context` prints the takeover block for a desk that carries one. [REQ: the-taking-over-desk-is-told-where-the-work-got-and-says-on-the-bus-that-it-took-over]
- [ ] 2.5 CORE — Interrupt: Esc, ~1 s, the fixed line with room and timestamp, ~0.8 s, CR — through the owner's `write`. [REQ: a-stalled-desk-is-interrupted-before-it-is-replaced]
- [ ] 2.6 CORE — Replace: stop the old desk through the owner, end its mandate `replaced`, start a desk with the takeover mandate through the resolver, re-point the engagement. [REQ: a-gone-or-still-stalled-desk-is-replaced-by-a-desk-that-takes-the-request-over]
- [ ] 2.7 CORE — `fleet_takeover_max` bound; past it nothing is done and the decision says `bound-reached`. [REQ: takeovers-per-request-are-bounded]
- [ ] 2.8 TEST — Unit tests for the decision table, the CPU rate, the context block, the record transitions; mutation-checked. [REQ: a-desk-is-stalled-only-when-nothing-shows-it-working]

## 3. Service wiring

- [ ] 3.1 CORE — `api/fleet_mandate.py`: `takeover_round()` (returns at once with no open engagement) and `takeover_loop` at 60 s, started beside the sweep loop. [REQ: a-gone-or-still-stalled-desk-is-replaced-by-a-desk-that-takes-the-request-over]
- [ ] 3.2 CORE — Logging: every decision with engagement id, desk label, reason, movement age, CPU rate (or `unmeasured`); never request text. [REQ: a-desk-is-stalled-only-when-nothing-shows-it-working]

## 4. Live verification

- [ ] 4.1 LIVE — Restart the dashboard service; confirm its start time is after the commit. [REQ: a-gone-or-still-stalled-desk-is-replaced-by-a-desk-that-takes-the-request-over]
- [ ] 4.2 LIVE — End to end: a request to a desk whose turn is made to hang; observe interrupt, then (if forced) replace, the handover FACT on the bus, and the linked answer closing the engagement. Record in `measurements.md`. [REQ: a-gone-or-still-stalled-desk-is-replaced-by-a-desk-that-takes-the-request-over]
- [ ] 4.3 LIVE — A desk running a CPU-busy command past the stall bound is NOT interrupted. Record. [REQ: a-desk-is-stalled-only-when-nothing-shows-it-working]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN a desk with an open engagement has not moved past the stall bound and its background CPU is below the bound THEN it is judged stalled [REQ: a-desk-is-stalled-only-when-nothing-shows-it-working, scenario: a-hung-tool-call]
- [ ] AC-2: WHEN a desk has not moved but a process it started uses CPU above the bound THEN it is judged working and nothing is done [REQ: a-desk-is-stalled-only-when-nothing-shows-it-working, scenario: a-long-test-run]
- [ ] AC-3: WHEN a stalled desk's engagement was never escalated THEN the turn is interrupted, the line typed, the interrupt time recorded [REQ: a-stalled-desk-is-interrupted-before-it-is-replaced, scenario: first-escalation]
- [ ] AC-4: WHEN an engagement passes the ceiling unescalated while its desk moves THEN it is interrupted once and nothing is replaced [REQ: a-stalled-desk-is-interrupted-before-it-is-replaced, scenario: the-hard-ceiling]
- [ ] AC-5: WHEN an open engagement's desk is no longer live THEN a new desk takes it over and the engagement names it [REQ: a-gone-or-still-stalled-desk-is-replaced-by-a-desk-that-takes-the-request-over, scenario: the-desk-died]
- [ ] AC-6: WHEN an engagement interrupted one stall bound ago is unanswered and its desk still stalled THEN the old desk is stopped, its mandate ends `replaced`, a new desk takes over [REQ: a-gone-or-still-stalled-desk-is-replaced-by-a-desk-that-takes-the-request-over, scenario: the-interrupt-did-not-help]
- [ ] AC-7: WHEN after the interrupt the desk moved or the engagement was answered THEN nothing is replaced [REQ: a-gone-or-still-stalled-desk-is-replaced-by-a-desk-that-takes-the-request-over, scenario: the-interrupt-helped]
- [ ] AC-8: WHEN a takeover desk starts a session THEN its context names room, timestamp, asker, predecessor seat and session, and the continue + handover-FACT instructions [REQ: the-taking-over-desk-is-told-where-the-work-got-and-says-on-the-bus-that-it-took-over, scenario: context-of-a-taking-over-desk]
- [ ] AC-9: WHEN the new desk posts an unlinked handover FACT THEN the engagement stays open until a linked reply [REQ: the-taking-over-desk-is-told-where-the-work-got-and-says-on-the-bus-that-it-took-over, scenario: the-handover-notice-does-not-close-the-request]
- [ ] AC-10: WHEN an engagement at the takeover maximum has a stalled desk THEN nothing is interrupted or started and it is listed waiting [REQ: takeovers-per-request-are-bounded, scenario: the-bound-is-reached]
- [ ] AC-11: WHEN a listing misses a desk whose unit is active THEN its mandate stays open [REQ: a-mandate-is-ended-for-a-missing-agent-only-when-its-unit-is-measured-gone, scenario: a-listing-misses-a-running-desk]
- [ ] AC-12: WHEN a listing misses a desk whose unit is inactive THEN its mandate is ended [REQ: a-mandate-is-ended-for-a-missing-agent-only-when-its-unit-is-measured-gone, scenario: the-desk-really-exited]
- [ ] AC-13: WHEN the start is refused for a held label and the newest desk mandate under it is ended with an active unit THEN it is re-opened and the request resolves to that desk [REQ: a-running-desk-whose-mandate-was-ended-is-re-adopted-not-blocked, scenario: held-label-ended-mandate]
- [ ] AC-14: WHEN a quiet desk has an open engagement it asked THEN the sweep keeps it with `asking-open` [REQ: a-desk-waiting-on-its-own-request-is-not-swept, scenario: desk-asked-another-project]
