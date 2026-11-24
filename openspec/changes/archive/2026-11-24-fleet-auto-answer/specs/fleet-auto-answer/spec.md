## IN SCOPE
- A decider outbound that answers a relayed blocking point (an agent's question, or a finished turn's continuation question) on the operator's behalf
- Looking the answer up in the asking project's information — through the project knowledge-base search and the fixed decision locations — and the operator's earlier decisions, with three tiers: decided, found, likely
- Hard exclusions: outward or irreversible steps, and every permission prompt
- A proposal window: the automatic answer is shown before it is written, and a human answer wins
- Forwarding to the operator's real outbound, with the decider's recommendation attached
- The relay handing its outbound the call's kind, session id and working directory
- A machine switch and a floating panel on the fleet header (pending proposals with cancel, recent decisions); the pending proposal marked on the agent
- A machine-local decision log of what was asked and what was answered
- The fork ends after its answer and leaves no process or session behind

## OUT OF SCOPE
- Changing the relay hooks, the chat bridge, or the envelope the bridge reads — except the two relay-side changes the requirements below name: the call's kind, session and working directory handed to the outbound, and no continuation for a headless run
- Answering a permission prompt automatically (forwarded with a recommendation only)
- Learning from answers over time, or storing a profile of the operator
- Answering inside a session that is not wired to the relay (the in-session keep-going hook is a separate mechanism)
- Any action other than writing an answer to the relay's answer store, or releasing a finished turn's call through the relay's own release request

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
For each question the decider SHALL produce one choice and a tier: `decided` when an earlier operator decision covers it, `found` when the answer is written in the project's information, `likely` when it is inferred. The tier SHALL be derived from CHECKED references, not taken from the model: a conversation reference counts only if its quote occurs verbatim in an operator turn of the session before the question, and a file reference only if its excerpt occurs verbatim in that file. `decided` SHALL require at least one checked operator quote or recorded decision; `found` at least one checked file excerpt; a choice whose references all fail the check SHALL be treated as `likely`. A `likely` choice SHALL carry a confidence between 0 and 1. A choice for a question with a closed option list SHALL be one of those options; a continuation's choice MAY be free text. A decision without a choice, or a closed-list choice outside the list, SHALL be treated as no decision.

#### Scenario: A decision already on record
- **WHEN** the project's rules state the operator's decision that answers the question
- **THEN** the choice is that option, the tier is `decided`, and the source names the file and quotes the decision

#### Scenario: A reference that does not check out
- **WHEN** the fork claims tier `decided` and quotes an operator message that does not occur in the transcript
- **THEN** the tier used is `likely`, and the answer is written only if its confidence is at or above `likely_min`

#### Scenario: An answer outside the options
- **WHEN** the model returns a choice that is not one of the question's options
- **THEN** no automatic answer is made and the question is forwarded unchanged

### Requirement: The lookup reads where decisions live, and only reads
Before the decision, the decider SHALL run the project knowledge-base search (`set-kb search --json`) in the asking session's working directory with the question and its options, and SHALL hand the ranked sections (path, heading, excerpt) to the decision as candidate sources. When the knowledge base cannot search in that project, the decider SHALL continue without it and SHALL log that it did. The decision SHALL be made by a fork of the asking session (the session's conversation resumed into a new session id, the original left unchanged), on the same model and provider as the original session — `auto_answer.model` SHALL apply only to the fallback — with read-only file tools only, hooks disabled, the relay's guard set, and a time bound. The fork SHALL be asked for the operator's answer and for references, each either an operator message quoted from the conversation or a file path with an excerpt; it SHALL also be pointed at the instruction files of the project and of the user, the project's rules directory, the session's newest handoff, the open OpenSpec changes, the bug register, the project's memory directory, and any paths listed in `auto_answer.extra_paths`. When the session cannot be forked, the decider SHALL fall back to one headless call in the session's working directory with the same sources and SHALL log the fallback. A decision that fails or times out SHALL produce no decision.

#### Scenario: The knowledge base finds the answer
- **WHEN** the answer to the question is written in a section of the project's documentation that is not one of the fixed locations
- **THEN** that section is among the candidates the model receives, and a `found` choice names it as its source

#### Scenario: The knowledge base cannot search
- **WHEN** `set-kb` reports that search does not work in the asking project
- **THEN** the decision is made from the fixed locations alone and the log records that the knowledge base was not used

#### Scenario: The fork answers with the operator's own words
- **WHEN** the operator stated the decision earlier in the same session, and it is written nowhere else
- **THEN** the fork's choice is that option, and its reference quotes the operator's message

#### Scenario: The fork keeps the session's model
- **WHEN** the asking session runs on a given model through a given provider
- **THEN** the fork runs on that same model through that same provider, whatever `auto_answer.model` says

#### Scenario: The original session is untouched
- **WHEN** the decider forks a session to decide
- **THEN** the original session's transcript gains no entry from the fork

#### Scenario: The model call times out
- **WHEN** the headless call does not answer within its bound
- **THEN** the question is forwarded unchanged and no answer is written

### Requirement: A standing delegation is decided on, not waited for
When the machine names the operator's standing decisions (`auto_answer.standing`, `path#heading` entries), the decider SHALL put each named section into the prompt verbatim and SHALL instruct the model that a question the delegation covers is decided by choosing the option that moves the work forward — the agent's own recommended option unless a citable source contradicts it — with tier `decided` and a decision reference quoting the standing decision. The model SHALL still abstain on what the standing decision reserves, on matters of strategy or taste (a release version, a public statement, money, people), and when the options conflict with something the operator said. Each abstention SHALL be logged with the model's one-line reason.

#### Scenario: An in-project step under a delegation
- **WHEN** a finished turn suggests running the project's tests and the standing decision says in-project testing never waits
- **THEN** the decider proposes that step with tier `decided`, citing the standing decision

#### Scenario: A finished turn with nothing worth doing
- **WHEN** a continuation's suggestions only re-check finished work and the model answers `done`
- **THEN** nothing is posted to the channel, the call is released so the session stays idle, and the log records the outcome `closed`

### Requirement: A headless run is not continued
The continuation relay SHALL NOT ask "what next?" for a session started headless (`claude -p`), recognised by the runtime's `CLAUDE_CODE_ENTRYPOINT` being set to anything other than `cli`: such a run exits when its turn ends, so there is no session to continue.

#### Scenario: A timer's check run ends its turn
- **WHEN** a `claude -p` run's turn ends with the verdict DONE
- **THEN** no continuation is posted and no waiting record is written

### Requirement: Outward and irreversible steps are never answered automatically
The decider SHALL NOT write an answer when the blocking point is a permission prompt, or when either check marks the step as outward or irreversible: a deterministic pattern check over the chosen answer — and over the question too when the answer is consent ("yes", "mehet", or three words or fewer), so the act the question names is checked — (covering at least publishing or pushing, deploying, production, sending a message or email, deleting, paying, and credentials, plus `auto_answer.never_patterns`), or the model's own flag. Options that were not chosen SHALL NOT exclude; a mention in the question preceded by a negator ("nothing is pushed") SHALL NOT exclude; a noun of the act inside a read-only answer ("check whether the deletion finished") SHALL NOT exclude; an act the answer reserves for the operator in the same clause, joined to "ask me" or "kérdezz meg" by filler words only ("run the tests; ask me before you publish") SHALL NOT exclude; a noun that only names a message ("üzenet") SHALL NOT exclude as sending. Any other verb of the act in the answer always excludes, and no general negation check is applied to the answer ("No, publish it now" excludes). A machine MAY list exclusion families its operator does not want to be asked about in `auto_answer.allow_families` (only `push` is separable this way; a force-push belongs to deleting and is never allowed by it); the model is told so, and its own flag still excludes. In those cases the question SHALL be forwarded with the decider's recommendation, its tier and its source attached, and SHALL wait for a human answer.

#### Scenario: The agent asks whether to push
- **WHEN** an agent asks "may I push the 11 commits?" and the record shows the operator approved pushes before
- **THEN** no automatic answer is written; the operator receives the question with the recommendation and its source

#### Scenario: A permission prompt
- **WHEN** the permission carrier relays a tool permission
- **THEN** no automatic answer is written, whatever the tier

#### Scenario: Only the pattern fires
- **WHEN** the model marks the step as not outward but the question mentions deploying and the answer is "Yes"
- **THEN** no automatic answer is written

#### Scenario: An outward option that was not chosen
- **WHEN** the options are "Leave as is", "Install both" and "Push set-core", the question says nothing is pushed yet, and the chosen answer is "Install both"
- **THEN** the pattern check does not exclude the answer

#### Scenario: An act the answer keeps for the operator
- **WHEN** the chosen continuation is "Re-run the check; ask me only the publish yes for the site"
- **THEN** the pattern check does not exclude the answer
- **AND** "Ask me nothing and publish it" and "Ask me later; publish now" are still excluded

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

### Requirement: The fork ends after its answer
The fork that makes the decision SHALL be a non-interactive run that ends when it has answered, and SHALL leave no process behind: when its time bound expires, the decider SHALL terminate the fork's whole process group. The fork SHALL NOT be listed as a fleet agent, SHALL NOT take a bus seat, and SHALL NOT leave a resumable session behind.

#### Scenario: The fork answers
- **WHEN** the fork returns its decision
- **THEN** no process of the fork is alive afterwards, and no new session transcript remains

#### Scenario: The fork overruns its bound
- **WHEN** the fork has not answered when its time bound expires
- **THEN** its process group is terminated, no process of it remains, and the question is forwarded without a decision

### Requirement: Every decision is logged with what was asked and what was answered
The decider SHALL append one record per relayed question to a machine-local decision log that is never written into any repository: the time, project, agent and session, the kind, the question and its options, the decision (choice, derived tier, confidence), the checked and the failed references, the outcome (written, excluded, below the bar, cancelled, overtaken by a human answer, no decision, fallback used) and, when a human answered, that answer. The log file SHALL be readable only by its owner and SHALL be pruned after `auto_answer.log_days` (default 90). The relay's own journal SHALL continue to carry no question or answer text.

#### Scenario: An automatic answer is written
- **WHEN** the decider writes an answer after the window
- **THEN** the decision log holds the question, the options, the written answer, its tier and its checked references, with the outcome `written`

#### Scenario: A human answers first
- **WHEN** the operator answers during the window
- **THEN** the decision log records the proposal, the outcome `overtaken` and the operator's answer

### Requirement: The fleet carries a switch and a panel of decisions
The fleet header SHALL carry one control for automatic answering, next to the question-relay switch: it SHALL show whether automatic answering is on and the number of pending proposals, and it SHALL open a floating panel in the manner of the relation map — above the layout, moving nothing under it, with its own close control. The panel SHALL hold the on/off switch, the pending proposals (agent, question, proposed answer, tier, references, remaining time, a cancel control) and the recent decisions from the decision log (time, agent, question, answer, tier, outcome), newest first. The pending proposal SHALL also be marked on the asking agent. Cancelling SHALL leave the question waiting for a human answer. Every proposal the panel shows — also an excluded or below-the-bar one — SHALL carry a send control that writes the proposed answer at once as the OPERATOR's own answer: it is the person's act, so no exclusion, bar or window applies, and the log records it with the operator's answer equal to the proposal. It SHALL refuse, with the reason, when there is no proposal or the question no longer waits.

#### Scenario: The operator sends a held proposal
- **WHEN** an excluded proposal is shown and the operator presses its send control
- **THEN** the proposed answer is written as the operator's answer and the question ends
- **AND** pressing send for a call that no longer waits is refused with the reason, and nothing is written

#### Scenario: Cancel from the panel
- **WHEN** the operator cancels a pending proposal in the panel
- **THEN** the decider does not write it, the agent's question still waits, and the decision log records `cancelled`

#### Scenario: The panel opens over the screen
- **WHEN** the operator opens the panel
- **THEN** it floats above the fleet and no element under it moves or changes size

#### Scenario: A pending proposal is counted where the reader stands
- **WHEN** a proposal is pending and the panel is closed
- **THEN** the header control shows the count of pending proposals
