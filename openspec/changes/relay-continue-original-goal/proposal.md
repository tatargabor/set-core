## Why

When a session ends its turn as finished, the relay posts "what next?" with up to three
suggestions taken from the final message alone. The owner reports that these stops are often
only intermediate stops on the agent's side: the agent declares `ALL DONE` for the board or
the step it was looking at, while the goal the session was started for is still open. Nothing
in the post reminds the owner of that goal, and none of the options says "keep going". So
work that could continue waits for the owner to remember why the session exists and type it
out. The owner's request, 2026-11-27: when there is something to continue, ask whether the
goals and the reason for starting the session still hold, and whether to carry on.

## What Changes

- The continuation's suggester also reads the session's opening prompt (the reason it was
  started), and returns a `GOAL:` line naming what the session was started for, when the
  prompts show it.
- The continuation post shows `Started for: <goal>` and asks whether that goal and its reason
  still hold.
- The post's first option is always a fixed "keep going toward the original goal" option. The
  model's suggestions follow it, at most three.
- Picking that option wakes the session with an instruction to re-check its original goal and
  the reason it was started. If they still hold and work is left, the session carries on with
  the next step. If not, it says why in one line and stops.
- Unchanged: the post appears only after a DONE verdict, the terminal stays live, a typed
  prompt supersedes it, and no prompt, goal or summary text is persisted or logged.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `agent-question-relay`: ADDED requirements on what the continuation post asks and offers.
  They are added rather than modified because the continuation requirement itself still lives
  in the unarchived `relay-answerable-blocking-points` change.

## Impact

- `lib/set_orch/fleet/continuation.py`: suggester prompt and parsing, opening-prompt reader,
  question text, fixed option, and the wake instruction for it.
- `tests/unit/test_continuation_relay.py`: new cases.
- The auto-answer treats the new option like any continuation option. Whether it may pick it
  is decided by its existing rules, and that decision is unchanged.
