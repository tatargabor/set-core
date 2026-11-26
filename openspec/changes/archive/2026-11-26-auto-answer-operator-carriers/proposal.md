## Why

Measured 2026-11-26 over the decision log: of 43 operator quotes the reference check refused,
42 were in the session's own transcript, in carriers the check never read — a prompt typed
while the agent worked (`queued_command`), the operator's answers in an `AskUserQuestion`
result, and the relay's continuation instruction inside its Stop-hook notification. The 43rd
was the fork quoting him with his typos corrected. A refused quote makes a correct decision
`likely`, and the model's own 0.5–0.6 put it below the bar: the decider did not answer what
the operator had already decided (bug register B-245, B-240).

## What Changes

- An operator turn is what the operator said in any of four carriers: a typed prompt, a
  prompt queued while the agent worked (human origin only), the answers — never the question
  text — of a question dialog, and the relay's continuation instruction.
- A peer session's or subagent's message is not an operator turn.
- What the automatic answer itself wrote into the session is not an operator turn.
- A quote checks out when it matches word for word, ignoring case, accents and punctuation,
  with one typo per word of five or more letters (two at nine or more); short words must be
  exact, and no word may be added or dropped.

## Capabilities

### Modified Capabilities

- `fleet-auto-answer`: the reference check's notion of an operator turn and of a match.

## Impact

`lib/set_orch/fleet/auto_answer.py` (`operator_turns`, `quote_in`, `own_written_answers`),
`auto_answer_worker.log_path` delegates to `auto_answer.decision_log_path`. No config, no
route, no UI change.
