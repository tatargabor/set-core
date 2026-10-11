## 1. Detector

- [x] 1.1 `lib/set_orch/fleet/wait_detect.py`: `classify(message)` (headless small model, hooks disabled, no persistence, timeout, exact-word parse) and `decide(hook_input)` with injectable classifier; logging without message text [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question]
- [x] 1.2 Guards: relay off/not ready, `stop_hook_active`, empty message, inside the classifier [REQ: the-detector-acts-only-while-the-relay-is-on-and-ready]
- [x] 1.3 Every classifier failure → no output [REQ: every-classifier-failure-lets-the-turn-end]
- [x] 1.4 `bin/set-hook-wait-detect`; `install.sh` link list [REQ: the-detector-acts-only-while-the-relay-is-on-and-ready]
- [x] 1.5 `bin/set-deploy-hooks`: Stop matcher-"" entry, timeout 60, base check [REQ: the-detector-reaches-every-project]

## 2. Tests

- [x] 2.1 `tests/unit/test_wait_detect.py`: guards, waiting → block with the instruction, done → nothing, every failure → nothing, no message text in logs, deploy twice; mutation round [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question]

## 3. Live verification

- [x] 3.1 Real session, real classifier, stand-in bridge via environment overrides: a manual-step wait is converted and answered; a finished turn is left alone; relay off → nothing [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question]
- [x] 3.2 Roll the hook out to every tree (same procedure as the relay) [REQ: the-detector-reaches-every-project]
- [ ] 3.3 One real wait answered by the user on Discord [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question]

## Acceptance Criteria (from spec scenarios)

### The detector acts only while the relay is on and ready
- [x] AC-1: WHEN a turn ends and the relay is off THEN no output and no classifier [REQ: the-detector-acts-only-while-the-relay-is-on-and-ready, scenario: relay-off]
- [x] AC-2: WHEN stop_hook_active is true THEN no output [REQ: the-detector-acts-only-while-the-relay-is-on-and-ready, scenario: already-continued-once]

### A turn that ends waiting on the user is turned into a structured question
- [x] AC-3: WHEN the final message ends with a manual-step wait THEN the stop is blocked with the re-ask instruction [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question, scenario: a-manual-step-wait]
- [x] AC-4: WHEN the classifier says not waiting THEN no output [REQ: a-turn-that-ends-waiting-on-the-user-is-turned-into-a-structured-question, scenario: a-finished-turn]

### Every classifier failure lets the turn end
- [x] AC-5: WHEN the classifier times out THEN no output [REQ: every-classifier-failure-lets-the-turn-end, scenario: classifier-times-out]

### The detector reaches every project
- [x] AC-6: WHEN deployed twice THEN exactly one detector hook [REQ: the-detector-reaches-every-project, scenario: deploy-twice]

## Verification record (2026-10-11)

- `pytest tests/unit/test_wait_detect.py` — 17 passed; with the relay's tests 41. Mutation round: 10 mutants (no `stop_hook_active` guard, readiness reduced to "enabled", no classifier-session guard, "not DONE" treated as waiting, any classifier text accepted, a failed classifier run accepted, session persistence on, guard env not set, message text in a log line, a blank message classified) — all 10 caught, after one case was strengthened: the non-zero-exit case printed nothing, so it would have been refused anyway; it now prints a valid word before failing.
- Spike before the build (real session): `last_assistant_message` and `stop_hook_active` are in the Stop input; a block makes the model re-ask with AskUserQuestion with its own fitting options; the continuation's Stop has `stop_hook_active: true`.
- **Live, real classifier, stand-in bridge via environment overrides:** a manual-step wait ending "Then tell me 'done'" → classified WAITING in 3.3 s → the agent re-asked with the steps written into the question and a "Done" option → the relay carried it → answered → the continued turn ended without a second classification. A finished turn ("What is 17 times 3?") → DONE in 5.2 s, left alone. Relay off → the hook printed nothing and wrote nothing.
- Rollout with the relay's procedure: 53 trees committed (`.claude/settings.json` only, the detector entry the only change, checked per tree), the same 3 left uncommitted, re-plan: present in all 56. Nothing pushed.

**Open:** 3.3 — one real wait answered on Discord by the user.
