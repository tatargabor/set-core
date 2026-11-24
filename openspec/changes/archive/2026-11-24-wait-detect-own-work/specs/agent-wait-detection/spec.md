## MODIFIED Requirements

### Requirement: A turn that ends waiting on the user is turned into a structured question

While the relay is on and ready, the hook SHALL classify the final message with a small
model (`question_relay.classifier_model`, default `haiku`), run headless with all hooks
disabled and no session persisted. The classifier SHALL answer one of three words: WAITING
(the agent's next step is blocked on the user), SELF (the next step waits only on work the
agent started itself or asked another agent for, which wakes it), or DONE. A message that
waits on its own work and also asks the user something it needs SHALL be WAITING. Only when
the classifier answers WAITING SHALL the hook return `decision: "block"`, with a reason
instructing the agent to ask again with `AskUserQuestion`, putting into the question the
context needed to answer without the terminal and offering short options that fit. A SELF
verdict SHALL be recorded as SELF, so that neither the re-ask nor the continuation acts on it.

#### Scenario: A manual-step wait

- **WHEN** the relay is on and the final message lists steps and ends "Then tell me 'done'"
- **THEN** the hook blocks the stop with the re-ask instruction

#### Scenario: A finished turn

- **WHEN** the classifier answers that the agent is not waiting
- **THEN** the hook exits with no output and the turn ends

#### Scenario: A turn waiting on its own background work

- **WHEN** the final message says the agent continues once its own subagent, build or bus reply arrives, and asks the user nothing
- **THEN** the classifier answers SELF, the hook exits with no output, and the recorded verdict is SELF

### Requirement: Every classifier failure lets the turn end

If the classifier cannot be started, exceeds its timeout, exits non-zero, or answers
anything other than the three expected words, the hook SHALL exit 0 with no output.
Diagnostics SHALL name the outcome and the latency, never the message text.

#### Scenario: Classifier times out

- **WHEN** the classifier does not answer within its timeout
- **THEN** the turn ends as it would without the hook
