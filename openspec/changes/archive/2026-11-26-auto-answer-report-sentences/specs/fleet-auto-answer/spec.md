## MODIFIED Requirements

### Requirement: Outward and irreversible steps are never answered automatically
The decider SHALL NOT write an answer when the blocking point is a permission prompt, or when either check marks the step as outward or irreversible: a deterministic pattern check over the chosen answer — and over the question too when the answer is consent ("yes", "mehet", or three words or fewer), so the act the question names is checked — (covering at least publishing or pushing, deploying, production, sending a message or email, deleting, paying, and credentials, plus `auto_answer.never_patterns`), or the model's own flag. Options that were not chosen SHALL NOT exclude; a mention in the question preceded by a negator ("nothing is pushed") SHALL NOT exclude; a noun of the act inside a read-only answer ("check whether the deletion finished") SHALL NOT exclude; an act the answer reserves for the operator in the same clause, joined to "ask me" or "kérdezz meg" by filler words only ("run the tests; ask me before you publish") SHALL NOT exclude; a noun that only names a message ("üzenet") SHALL NOT exclude as sending. In the question, a sentence that reports finished work (it says done, ready, passed, merged, already — "kész", "megvan", "zöld", "PASS") SHALL NOT exclude, unless the act in it is one the speaker still means to do (a first-person, subjunctive or imperative verb: "kész, elküldöm a vevőnek") or the sentence itself asks ("?"); and pictures, renders or results the agent sends back to the operator ("és küldöm a képeket", "I'll send you the renders") with no other recipient in the clause SHALL NOT exclude as sending. A Hungarian verbal prefix SHALL NOT hide an act: "elküldöm", "kiküldjem", "kitörlöm" are sending and deleting. Any other verb of the act in the answer always excludes, and no general negation check is applied to the answer ("No, publish it now" excludes). A machine MAY list exclusion families its operator does not want to be asked about in `auto_answer.allow_families` (only `push` is separable this way; a force-push belongs to deleting and is never allowed by it); the model is told so, and its own flag still excludes. In those cases the question SHALL be forwarded with the decider's recommendation, its tier and its source attached, and SHALL wait for a human answer.

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

#### Scenario: A report of finished work beside the question
- **WHEN** the question reads "A B-233 javítás kész és élesben megy (verify PASS, archive, push). … Újraindítsam a watch-ot?" and the decider chooses «Indítsd újra (Recommended)»
- **THEN** the report sentence does not exclude, and the answer is written if its tier allows

#### Scenario: Pictures sent back to the operator
- **WHEN** an approval request ends "Ha mehet, megírom a kódot, lefuttatom a dev mold-ot, és küldöm a képeket." and the decider chooses «Mehet»
- **THEN** sending the pictures to the operator does not exclude, while "elküldöm a képeket a vevőnek" would

#### Scenario: A verbal prefix does not hide the act
- **WHEN** the question asks "A tervezet kész, elküldöm a vevőnek. Mehet?" and the decider chooses «Mehet»
- **THEN** the answer is excluded as sending
