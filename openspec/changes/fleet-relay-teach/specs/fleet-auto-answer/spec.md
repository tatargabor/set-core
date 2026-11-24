## MODIFIED Requirements

### Requirement: A standing delegation is decided on, not waited for
When the machine names the operator's standing decisions (`auto_answer.standing`, `path#heading` entries), the decider SHALL put each named section into the prompt verbatim and SHALL instruct the model that a question the delegation covers is decided by choosing the option that moves the work forward — the agent's own recommended option unless a citable source contradicts it — with tier `decided` and a decision reference quoting the standing decision. The decider SHALL also put the asking project's taught rules (`.claude/rules/auto-answer-taught.md` in its main checkout, and in the call's own tree when that differs) into the prompt verbatim, labelled as rules the operator taught for that project. A question a taught rule covers SHALL be answered with the rule's answer when the rule's stated condition holds, with tier `decided` and a decision reference quoting the rule; when the condition cannot be confirmed from the session or the sources, the model SHALL abstain and say which condition is open. The model SHALL still abstain on what the standing decision reserves, on matters of strategy or taste (a release version, a public statement, money, people), and when the options conflict with something the operator said. Each abstention SHALL be logged with the model's one-line reason.

#### Scenario: An in-project step under a delegation
- **WHEN** a finished turn suggests running the project's tests and the standing decision says in-project testing never waits
- **THEN** the decider proposes that step with tier `decided`, citing the standing decision

#### Scenario: A finished turn with nothing worth doing
- **WHEN** a continuation's suggestions only re-check finished work and the model answers `done`
- **THEN** nothing is posted to the channel, the call is released so the session stays idle, and the log records the outcome `closed`

#### Scenario: A taught rule covers the question
- **WHEN** the project's taught rules hold "commit to the feature branch: yes, always" and an agent asks whether to commit there
- **THEN** the decider proposes "yes" with tier `decided`, quoting the taught rule

### Requirement: Outward and irreversible steps are never answered automatically
The decider SHALL NOT write an answer when the blocking point is a permission prompt, or when either check marks the step as outward or irreversible: a deterministic pattern check over the chosen answer — and over the question too when the answer is consent ("yes", "mehet", or three words or fewer), so the act the question names is checked — (covering at least publishing or pushing, deploying, production, sending a message or email, deleting, paying, and credentials, plus `auto_answer.never_patterns`), or the model's own flag. Options that were not chosen SHALL NOT exclude; a mention in the question preceded by a negator ("nothing is pushed") SHALL NOT exclude; a noun of the act inside a read-only answer ("check whether the deletion finished") SHALL NOT exclude; an act the answer reserves for the operator in the same clause, joined to "ask me" or "kérdezz meg" by filler words only ("run the tests; ask me before you publish") SHALL NOT exclude; a noun that only names a message ("üzenet") SHALL NOT exclude as sending. Any other verb of the act in the answer always excludes, and no general negation check is applied to the answer ("No, publish it now" excludes). A machine MAY list exclusion families its operator does not want to be asked about in `auto_answer.allow_families` (only `push` is separable this way; a force-push belongs to deleting and is never allowed by it); the model is told so, and its own flag still excludes. One exception, decided by the owner on 2026-11-24 (*„Mindig mehet"*): an answer whose checked references include a decision quote from the project's taught-rules file SHALL NOT be excluded by the pattern check nor by the model's flag. A taught rule is the operator's own answer given in advance. A permission prompt SHALL stay excluded whatever a rule says. In those cases the question SHALL be forwarded with the decider's recommendation, its tier and its source attached, and SHALL wait for a human answer.

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

#### Scenario: A taught rule approves an outward step
- **WHEN** the project's taught rules say a site may go live once its design change is verified, an agent asks whether to put it live and says the change is verified, and the decider answers "yes" quoting the rule
- **THEN** the answer is allowed and proposed for writing, although "live" and "production" are outward words

#### Scenario: A rule does not open a permission prompt
- **WHEN** a permission prompt waits and a taught rule seems to cover it
- **THEN** the prompt is still excluded and forwarded to the operator
