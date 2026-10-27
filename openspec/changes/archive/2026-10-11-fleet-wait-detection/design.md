## Context

The relay (`agent-question-relay`) carries `AskUserQuestion`. A prose wait ends the turn
instead, and the measured facts in the proposal show the turn end can be intercepted and
converted into exactly the call the relay already carries.

## Goals / Non-Goals

**Goals:** a prose wait reaches the channel as a structured question, with options where
the question allows; the terminal and the relay keep working as today when anything fails.

**Non-Goals:** answering a prose wait without the re-ask; waits inside a turn.

## Decisions

**D1 — Convert, do not transport.** The hook does not post anything itself. It makes the
agent ask with `AskUserQuestion`, and the relay — with its switch, waiting record, release,
envelope and answer path — does the rest. One transport, one place to fix it.

**D2 — The agent writes the options.** Measured: told to re-ask, the model built fitting
options from its own question and put the steps into the question text. A detector that
extracted options from prose would be the "prose read as fact" defect class; the model that
wrote the prose is the one that knows what it asked.

**D3 — A small-model classifier, not a pattern.** Phrases such as "tell me" or a trailing
question mark appear in finished turns too ("if it still fails, tell me…"), and many waits
carry neither. The classifier runs only while the relay is on; its cost is one headless call
(~4 s) per turn end. Hooks are disabled in that call (`disableAllHooks`) and an environment
guard makes this hook a no-op inside it, so it cannot recurse; `--no-session-persistence`
keeps it out of the transcript store the fleet reads.

**D4 — Fail toward today.** Missing binary, timeout (25 s, inside the 60 s entry), non-zero
exit, or an answer that is not exactly one of the two words → the turn ends as without the
hook. A missed wait is the status quo; a false conversion costs one extra question.

**D5 — No rule file.** A rule asking agents to prefer `AskUserQuestion` would reach projects
only through a full `set-project init`, and would still be advisory. The hook enforces where
it matters (relay on). Left for later if conversions turn out frequent.

## Risks / Trade-offs

- [The reason shows as "Stop hook error: …" in the terminal] → the runtime's own label for
  a block reason; the text says what is happening.
- [One conversion per turn] → after the relayed answer the agent continues inside the same
  turn; a second prose wait in that continuation is not converted (`stop_hook_active`).
- [Classifier cost while the relay is on] → bounded by turn ends; off costs nothing.
