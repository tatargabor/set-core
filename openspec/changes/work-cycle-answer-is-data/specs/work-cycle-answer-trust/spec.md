## IN SCOPE

- How an answer's text enters a run's prompt, and what the prompt says it is.
- Bounds and validity: length, and conformance to the choices the question offered.
- Free-text fields of the answer document reaching diagnostics.

## OUT OF SCOPE

- How an answer arrives, is matched, deferred or quarantined — `deferred-work-connector` (in `work-cycle-engine-apply-first`).
- Who may write an answer, and any outbound that might carry one.
- B-36, a separate defect in the same module.

## ADDED Requirements

### Requirement: An answer enters a run as data, not as a standing instruction

An answer's text SHALL be delimited where it is rendered into a run's prompt, and the prompt
SHALL state that the text is a person's decision on the named question. The prompt SHALL NOT
present an answer's content as work to be carried out beyond deciding that question.

#### Scenario: An answer contains instruction-shaped text

- **WHEN** the same prompt is rendered twice, once with a benign answer and once with an
  answer of the same length whose text reads like a directive
- **THEN** the two prompts differ only inside the delimited answer block
- **AND** every other section — the task list, the instructions, the reading list — is
  byte-identical

#### Scenario: An answer contains the delimiter

- **WHEN** an answer's text contains the delimiting sequence
- **THEN** the rendered prompt still attributes the whole text to that one answer

### Requirement: A refused answer is a distinct outcome with a stated resting place

An answer refused by any rule in this specification SHALL be reported as refused with its
reason. It SHALL NOT be applied, SHALL NOT be marked consumed, SHALL NOT be quarantined, and
SHALL NOT count towards the budget of parse attempts that leads to quarantine.

#### Scenario: The same refused answer is seen again

- **WHEN** an intake pass refuses an answer and a later pass sees the same document
- **THEN** it is refused again with the same reason
- **AND** repeated refusal never turns into quarantine

#### Scenario: A refused answer is corrected

- **WHEN** the document is replaced by one that passes the rules
- **THEN** it is applied normally, having lost nothing to the earlier refusals

### Requirement: An answer is bounded, and an over-long one is refused rather than truncated

An answer's text SHALL be bounded in length. An answer exceeding the bound SHALL be refused
with a stated reason. It SHALL NOT be truncated into a shorter text and applied as though a
person had written it.

#### Scenario: The answer is longer than the bound

- **WHEN** an answer's text exceeds the bound
- **THEN** it is refused with a reason naming the bound and the length received
- **AND** no shortened form of it is applied

### Requirement: Where the question offered choices, the answer must be one of them

When the question that produced an awaiting task offered a closed set of choices, an answer
that is not one of those choices SHALL be refused with a stated reason.

#### Scenario: An answer outside the offered set

- **WHEN** the question offered a closed set and the answer matches none of it
- **THEN** the answer is refused with a reason naming the offered choices
- **AND** the task remains awaiting

#### Scenario: The question offered no closed set

- **WHEN** the question accepted free text
- **THEN** any answer within the length bound is accepted

### Requirement: Every free-text field of an answer document is bounded before it reaches a diagnostic

Every free-text field of an answer document SHALL be enumerated, and each SHALL be bounded and
sanitised before it appears in a log line. Naming only the answer's text is not sufficient.

#### Scenario: A field other than the answer text carries hostile content

- **WHEN** an answer document carries a long or control-character-bearing value in a field
  such as the name of its source
- **THEN** what reaches the log is bounded and sanitised

#### Scenario: A new field is added to the document

- **WHEN** the answer document gains a free-text field
- **THEN** the enumeration is what decides whether it is bounded, rather than the field being
  covered by omission
