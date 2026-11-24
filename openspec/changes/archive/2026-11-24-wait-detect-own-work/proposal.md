## Why

The Stop-hook wait detector asks a small model whether a finished turn waits on the user. The
answer has two words, WAITING or DONE. A turn whose next step waits only on the agent's OWN
background work has no word of its own. Examples: a subagent, a verifier, a build, a test run,
or a reply on the agent bus. Such a turn was often classified WAITING, and the agent was told
to ask the user a question it did not have.

Measured 2026-11-24 on a live session: "Once the verify result arrives I'll commit and archive"
was blocked with the re-ask instruction. Re-run with 3 samples on each of 8 real-shaped messages,
the two-word prompt was right 17/24:
- a bus-reply wait was WAITING 3/3;
- the real message was WAITING 1/3;
- a mixed message that also asked the user was DONE 2/3, so a real question was missed.

A three-word prompt was right 24/24.

## What Changes

- The classifier answers one of three words: WAITING (blocked on the user), SELF (waits only on
  work the agent started itself or asked another agent for, which wakes it), DONE.
- A message that waits on its own work AND asks the user something it needs is WAITING.
- Only WAITING blocks the stop. SELF is recorded as its own verdict, so the continuation carrier,
  which acts only on DONE, does not post a "what next?" for it either.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `agent-wait-detection`: the classifier's answer set and what each answer does.

## Impact

- `lib/set_orch/fleet/wait_detect.py`: the prompt, `classify`, `VERDICTS`.
- Tests: `tests/unit/test_wait_detect.py`, `tests/unit/test_continuation_relay.py`.
- No deploy step: the Stop hook imports the module on every run.
