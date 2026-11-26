## MODIFIED Requirements

### Requirement: The decision names its tier and its source
For each question the decider SHALL produce one choice and a tier: `decided` when an earlier operator decision covers it, `found` when the answer is written in the project's information, `likely` when it is inferred. The tier SHALL be derived from CHECKED references, not taken from the model: a conversation reference counts only if its quote matches an operator turn of the session before the question — word for word, ignoring case, accents and punctuation, with at most one typo in a word of five or more letters and two in a word of nine or more, a shorter word exact, and no word added or dropped. An operator turn is a prompt the operator typed (also one queued while the agent worked, of human origin only), the operator's answers in a question dialog's result (never its question text), or the relay's continuation instruction; a peer session's or a subagent's message is not, and neither is anything the automatic answer itself wrote into the session; and a file reference only if its excerpt occurs verbatim in that file. `decided` SHALL require at least one checked operator quote or recorded decision; `found` at least one checked file excerpt; a choice whose references all fail the check SHALL be treated as `likely`. A `likely` choice SHALL carry a confidence between 0 and 1. A choice for a question with a closed option list SHALL be one of those options; a continuation's choice MAY be free text. A decision without a choice, or a closed-list choice outside the list, SHALL be treated as no decision.

#### Scenario: A decision already on record
- **WHEN** the project's rules state the operator's decision that answers the question
- **THEN** the choice is that option, the tier is `decided`, and the source names the file and quotes the decision

#### Scenario: A reference that does not check out
- **WHEN** the fork claims tier `decided` and quotes an operator message that does not occur in the transcript
- **THEN** the tier used is `likely`, and the answer is written only if its confidence is at or above `likely_min`

#### Scenario: An answer outside the options
- **WHEN** the model returns a choice that is not one of the question's options
- **THEN** no automatic answer is made and the question is forwarded unchanged

#### Scenario: A quote the operator typed while the agent worked
- **WHEN** the operator typed the decision while the agent was working, so the runtime recorded it as a queued prompt
- **THEN** the fork's quote of it checks out and the tier is `decided`

#### Scenario: The automatic answer's own words are not evidence
- **WHEN** the fork quotes, as the operator's, a continuation the automatic answer wrote into the session earlier
- **THEN** the quote does not check out

#### Scenario: A quote with the operator's typos corrected
- **WHEN** the operator wrote „akkor a képernyősekezt vedd fel legyne meg!” and the fork quotes „akkor a képernyőseket vedd fel legyen meg!”
- **THEN** the quote checks out; a quote that adds or drops a `ne` or `nem` does not
