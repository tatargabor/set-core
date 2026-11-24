## 1. Core

- [ ] 1.1 `engagement.py`: `asker_wake` (one of the outcomes) and `asker_wake_at` kept by `_normalise`; `mark_asker_wake(id, outcome)`; `answered_unwoken()` lists answered engagements with no outcome yet. Tests. [REQ: the-asker-is-woken-once-when-its-request-is-answered]
- [ ] 1.2 `takeover.wake_decision(record, rows, now, off_here)` → (outcome, row): too-old, gone, not-fleet-held, busy, operator-present, off-here, moved, woken. Tests, one per outcome; a mutation of the "moved since" check is caught. [REQ: the-asker-is-woken-once-when-its-request-is-answered]
- [ ] 1.3 `takeover.owner_type(label, line)` (no Esc) and `wake_line(record)` (pointers only). Test that the line carries no text beyond room, timestamps and asker. [REQ: the-asker-is-woken-once-when-its-request-is-answered]
- [ ] 1.4 `takeover_round` also runs the wake pass (when there are answered-unwoken engagements; the inventory is read once). `busy` is not recorded, so the next round looks again. Logs carry ids and outcomes. [REQ: the-asker-is-woken-once-when-its-request-is-answered]

## 2. Live

- [ ] 2.1 A scratch fleet agent asks a project through `set-fleet-ask` and ends its turn; the reply arrives; within one round its terminal receives the line and it continues; the engagement says `woken`. Record it in `measurements.md`. B-215 updated. [REQ: the-asker-is-woken-once-when-its-request-is-answered]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN a request is answered while the asker sits idle THEN one line is typed, `woken` is recorded, and no second line follows [REQ: the-asker-is-woken-once-when-its-request-is-answered, scenario: the-reply-arrives-while-the-asker-sits-idle]
- [ ] AC-2: WHEN the asker moved after the reply THEN nothing is typed and `moved` is recorded [REQ: the-asker-is-woken-once-when-its-request-is-answered, scenario: the-asker-already-moved-on]
- [ ] AC-3: WHEN the asker is still working THEN nothing is typed that round and a later round decides again [REQ: the-asker-is-woken-once-when-its-request-is-answered, scenario: the-asker-is-still-working]
- [ ] AC-4: WHEN the operator typed there recently, or automatic answers are off there THEN nothing is typed and why is recorded [REQ: the-asker-is-woken-once-when-its-request-is-answered, scenario: the-operator-is-at-that-terminal]
- [ ] AC-5: WHEN the asker runs outside the fleet THEN nothing is typed and `not-fleet-held` is recorded [REQ: the-asker-is-woken-once-when-its-request-is-answered, scenario: the-asker-is-not-in-a-fleet-terminal]
