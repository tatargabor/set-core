## IN SCOPE
- A decider outbound that answers a relayed blocking point (an agent's question, or a finished turn's continuation question) on the operator's behalf
- Looking the answer up in the asking project's information and the operator's earlier decisions, with three tiers: decided, found, likely
- Hard exclusions: outward or irreversible steps, and every permission prompt
- A proposal window: the automatic answer is shown before it is written, and a human answer wins
- Forwarding to the operator's real outbound, with the decider's recommendation attached
- The relay handing its outbound the call's kind, session id and working directory
- A machine switch, also on the fleet header; the pending automatic answer on the agent, with cancel

## OUT OF SCOPE
- Changing the relay hooks, the chat bridge, or the envelope the bridge reads
- Answering a permission prompt automatically (forwarded with a recommendation only)
- Learning from answers over time, or storing a profile of the operator
- Answering inside a session that is not wired to the relay (the in-session keep-going hook is a separate mechanism)
- Any action other than writing an answer to the relay's answer store

## ADDED Requirements

### Requirement: The decider is the relay's outbound and forwards to the operator's
The framework SHALL provide an outbound command, `set-auto-answer`, that accepts the relay's envelope on standard input exactly as the configured outbound does, and SHALL pass the envelope on to the command configured as `auto_answer.forward_command`. When the switch `auto_answer.enabled` is off, the envelope SHALL be forwarded unchanged and no answer SHALL be written by the decider. The decider SHALL return to the relay without waiting for its decision, so the relay's hook is not held by the model call.

#### Scenario: Switch off
- **WHEN** `auto_answer.enabled` is false and a relayed question arrives
- **THEN** the forward command receives the envelope byte-for-byte and no answer file is written by the decider

#### Scenario: The relay is not held
- **WHEN** the relay runs the decider
- **THEN** the decider exits within a few seconds, before the decision is made

### Requirement: The relay tells its outbound what it is asking about
The relay SHALL export to the outbound process the kind of the blocking point (`ask`, `permission` or `continuation`), the asking session's id and its working directory, as environment variables. The envelope's fields SHALL be unchanged.

#### Scenario: A continuation is relayed
- **WHEN** the continuation carrier hands a question to the outbound
- **THEN** the outbound's environment names the kind `continuation`, the session id and the session's working directory, and the envelope carries no new field

### Requirement: The decision names its tier and its source
For each question the decider SHALL produce one choice and a tier: `decided` when an earlier operator decision covers it, `found` when the answer is written in the project's information, `likely` when it is inferred. A `decided` or `found` choice SHALL carry at least one source as a path and a verbatim excerpt; a `likely` choice SHALL carry a confidence between 0 and 1. A choice for a question with a closed option list SHALL be one of those options; a continuation's choice MAY be free text. A decision without a tier, a decided or found choice without a source, or a closed-list choice outside the list SHALL be treated as no decision.

#### Scenario: A decision already on record
- **WHEN** the project's rules state the operator's decision that answers the question
- **THEN** the choice is that option, the tier is `decided`, and the source names the file and quotes the decision

#### Scenario: An answer outside the options
- **WHEN** the model returns a choice that is not one of the question's options
- **THEN** no automatic answer is made and the question is forwarded unchanged

### Requirement: The lookup reads where decisions live, and only reads
The decider SHALL make its decision with one headless model call per question, run in the asking session's working directory, with read-only file tools only, hooks disabled, and no session persisted. The call SHALL be pointed at the instruction files of the project and of the user, the project's rules directory, the session's newest handoff, the open OpenSpec changes, the bug register, the project's memory directory, and any paths listed in `auto_answer.extra_paths`. The call SHALL be bounded in time; a call that fails or times out SHALL produce no decision.

#### Scenario: The model call times out
- **WHEN** the headless call does not answer within its bound
- **THEN** the question is forwarded unchanged and no answer is written

### Requirement: Outward and irreversible steps are never answered automatically
The decider SHALL NOT write an answer when the blocking point is a permission prompt, or when either check marks the step as outward or irreversible: a deterministic pattern check over the question, its options and the chosen answer (covering at least publishing or pushing, deploying, production, sending a message or email, deleting, paying, and credentials, plus `auto_answer.never_patterns`), or the model's own flag. In those cases the question SHALL be forwarded with the decider's recommendation, its tier and its source attached, and SHALL wait for a human answer.

#### Scenario: The agent asks whether to push
- **WHEN** an agent asks "may I push the 11 commits?" and the record shows the operator approved pushes before
- **THEN** no automatic answer is written; the operator receives the question with the recommendation and its source

#### Scenario: A permission prompt
- **WHEN** the permission carrier relays a tool permission
- **THEN** no automatic answer is written, whatever the tier

#### Scenario: Only the pattern fires
- **WHEN** the model marks the step as not outward but the question mentions deploying
- **THEN** no automatic answer is written

### Requirement: An automatic answer is proposed before it is written, and a human answer wins
When the decider has an allowed choice — tier `decided` or `found`, or tier `likely` with a confidence at or above `auto_answer.likely_min` — it SHALL forward the question with the proposed answer, its tier, its source and the time it will be written, and SHALL write the answer only after `auto_answer.window_s` seconds, and only if no answer for that question exists by then and the proposal was not cancelled. The decider SHALL never overwrite an answer that is already present.

#### Scenario: Nobody answers within the window
- **WHEN** an allowed choice is proposed and no human answer arrives within the window
- **THEN** the decider writes the answer to the relay's answer store and the agent continues with it

#### Scenario: The operator answers first
- **WHEN** the operator answers during the window
- **THEN** the decider writes nothing, and the agent receives the operator's answer

#### Scenario: A likely choice below the bar
- **WHEN** the tier is `likely` and the confidence is below `auto_answer.likely_min`
- **THEN** the question is forwarded with the recommendation and nothing is written

### Requirement: Without a forward command, an unanswerable question goes back to the terminal
When no forward command is configured and the decider makes no automatic answer, it SHALL ask the relay to release the question, so the normal picker appears at the terminal rather than waiting for the relay's timeout.

#### Scenario: No outbound and no decision
- **WHEN** `auto_answer.forward_command` is empty and the question is excluded
- **THEN** the session's question is released to its terminal

### Requirement: Every automatic answer is visible and cancellable on the fleet
The fleet SHALL show, on the asking agent, a pending automatic answer with its proposed option, tier and remaining time, and SHALL offer to cancel it; cancelling SHALL leave the question waiting for a human answer. The fleet header SHALL carry the machine switch next to the question-relay switch. The decider SHALL log each decision with the call id, tier, whether it was written, excluded, cancelled or overtaken, and the source paths — never the question or answer text.

#### Scenario: Cancel from the fleet
- **WHEN** the operator cancels a pending automatic answer on an agent
- **THEN** the decider does not write it, and the agent's question still waits

#### Scenario: The log carries no text
- **WHEN** an automatic answer is written
- **THEN** the log line names the call id, the tier and the source paths, and contains neither the question nor the answer
