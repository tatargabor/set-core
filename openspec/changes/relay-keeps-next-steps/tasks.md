## 1. Carry a timed-out next step

- [x] 1.1 `wait_one(timeout=, note=)`: a carrier's own bound; `note["timed_out"]` only for a time-only release
- [x] 1.2 `continue_turn(on_timeout=)`: on a timeout-only release, hand a job (session, cwd, project, transcript, armed, started, prompt_id, question, options); a failing hand-on leaves the session as before
- [x] 1.3 `relay_backfill.repull_continuation` (fleet-held only) and `run_continuation` (post again, keep the age, wait `CARRY_MAX_S`, type `continuation.instruction`); `run_job` routes `kind: continuation`; the hook passes it
- [x] 1.4 Tests: 3 continuation + 7 backfill; two mutations (the hand-on skipped, `timed_out` never set) each fail a test; 480 relay tests green
- [ ] 1.5 Live: a next step that reaches 3300 s stays on the board (`relay.log`: `question relay continuation [...]: the hook's time ran out; handed to a carrier`), and an answer to it is typed in

## Acceptance

- [ ] AC-1: WHEN a next step reaches the hook's limit in a fleet terminal THEN it stays on the board and a later answer is typed in [REQ: a-next-step-the-hook-lets-go-only-for-lack-of-time-is-carried-on, scenario: the-hook-s-time-runs-out-on-a-next-step]
- [x] AC-2 (unit: `test_a_next_step_the_operator_typed_past_is_not_carried`, `test_only_a_timeout_hands_a_next_step_on`): WHEN the session moved on THEN nothing is typed [REQ: a-next-step-the-hook-lets-go-only-for-lack-of-time-is-carried-on, scenario: the-session-moved-on]
- [x] AC-3 (unit: `test_repull_continuation_carries_only_a_fleet_held_session`): WHEN the session is not fleet-held THEN nothing is carried [REQ: a-next-step-the-hook-lets-go-only-for-lack-of-time-is-carried-on, scenario: not-held-by-the-fleet]
