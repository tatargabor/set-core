## 1. Core (`lib/set_orch/fleet/wait_detect.py`)

- [x] 1.1 The prompt names three words (WAITING, SELF, DONE) with the mixed-message rule; `classify` accepts the three; `VERDICTS` gains SELF; only WAITING blocks. [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question]
- [x] 1.2 Tests: the parser takes SELF and still refuses anything else; a SELF turn is not blocked and its verdict is recorded; the continuation posts nothing for SELF. A mutation that makes SELF block is caught. [REQ: every-classifier-failure-lets-the-turn-end]

## 2. Measured

- [x] 2.1 Old vs new prompt on 8 real-shaped messages, 3 samples each, with the real haiku: old 17/24, new 24/24; no control flipped the wrong way. Recorded in `design.md` D1 and the proposal. [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the final message ends "Then tell me 'done'" THEN the hook blocks with the re-ask instruction [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question, scenario: a-manual-step-wait]
- [x] AC-2: WHEN the classifier says the agent is not waiting THEN the turn ends [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question, scenario: a-finished-turn]
- [x] AC-3: WHEN the message waits only on the agent's own work THEN SELF, no block, verdict SELF recorded [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question, scenario: a-turn-waiting-on-its-own-background-work]
- [x] AC-4: WHEN the classifier times out THEN the turn ends as without the hook [REQ: every-classifier-failure-lets-the-turn-end, scenario: classifier-times-out]
