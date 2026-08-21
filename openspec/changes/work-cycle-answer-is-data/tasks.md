# Tasks

⚠ **This change is a precondition for `work-cycle-question-outbound`.** No outbound is wired
until it lands: wiring first would ship the hole rather than close it.

## 1. The answer as data

- [ ] 1.1 Render the answer inside an explicit delimiter, labelled as the person's decision on
      its named question [REQ: an-answer-enters-a-run-as-data-not-as-a-standing-instruction]
- [ ] 1.2 An answer containing the delimiting sequence still renders as one answer
      [REQ: an-answer-enters-a-run-as-data-not-as-a-standing-instruction]
- [ ] 1.3 A test feeds an instruction-shaped answer and asserts what the unit is told to do is
      unchanged — the assertion is about the RESULT, not about a sanitiser having run
      [REQ: an-answer-enters-a-run-as-data-not-as-a-standing-instruction]

## 2. Bounds and validity

- [ ] 2.1 Measure the longest legitimate answer on record before choosing the bound; a bound
      picked rather than measured is a guess
      [REQ: an-answer-is-bounded-and-an-over-long-one-is-refused-rather-than-truncated]
- [ ] 2.2 An over-long answer is refused with the bound and the received length, and no
      shortened form is applied
      [REQ: an-answer-is-bounded-and-an-over-long-one-is-refused-rather-than-truncated]
- [ ] 2.3 Where the question offered a closed set, an answer outside it is refused and the
      task stays awaiting
      [REQ: where-the-question-offered-choices-the-answer-must-be-one-of-them]
- [ ] 2.4 A free-text question accepts any answer within the bound; where the offered set
      cannot be recovered, the question is treated as free text rather than refusing everything
      [REQ: where-the-question-offered-choices-the-answer-must-be-one-of-them]

## 3. Refusal has a resting place

- [ ] 3.0 A refused answer is reported as refused, is NOT applied, NOT consumed, NOT
      quarantined, and does not count towards the parse-attempt budget; a corrected document
      is applied normally afterwards
      [REQ: a-refused-answer-is-a-distinct-outcome-with-a-stated-resting-place]

## 4. Diagnostics

- [ ] 4.1 Enumerate every free-text field of the answer document, and bound and sanitise each
      before it reaches a log line — `source` included (B-37)
      [REQ: every-free-text-field-of-an-answer-document-is-bounded-before-it-reaches-a-diagnostic]
- [ ] 4.2 A test feeds a hostile value in a field OTHER than the answer text and asserts what
      the journal contains
      [REQ: every-free-text-field-of-an-answer-document-is-bounded-before-it-reaches-a-diagnostic]

## 5. Evidence

- [ ] 5.1 Stash each fix and re-run its test: a test that passes without the fix proves nothing
      [REQ: an-answer-enters-a-run-as-data-not-as-a-standing-instruction]
- [ ] 5.2 Mutation-test the bound and the option check; both fail in the reassuring direction,
      where a refused answer and an accepted one look alike from outside
      [REQ: an-answer-is-bounded-and-an-over-long-one-is-refused-rather-than-truncated]

## Acceptance Criteria (from spec scenarios)

<!-- An answer enters a run as data, not as a standing instruction -->
- [ ] AC-1: WHEN the same prompt is rendered twice, once with a benign answer and once with an answer of the same length whose text reads like a directive THEN the two prompts differ only inside the delimited answer block and every other section — the task list, the instructions, the reading list — is byte-identical [REQ: an-answer-enters-a-run-as-data-not-as-a-standing-instruction, scenario: an-answer-contains-instruction-shaped-text]
- [ ] AC-2: WHEN an answer's text contains the delimiting sequence THEN the rendered prompt still attributes the whole text to that one answer [REQ: an-answer-enters-a-run-as-data-not-as-a-standing-instruction, scenario: an-answer-contains-the-delimiter]

<!-- A refused answer is a distinct outcome with a stated resting place -->
- [ ] AC-3: WHEN an intake pass refuses an answer and a later pass sees the same document THEN it is refused again with the same reason and repeated refusal never turns into quarantine [REQ: a-refused-answer-is-a-distinct-outcome-with-a-stated-resting-place, scenario: the-same-refused-answer-is-seen-again]
- [ ] AC-4: WHEN the document is replaced by one that passes the rules THEN it is applied normally, having lost nothing to the earlier refusals [REQ: a-refused-answer-is-a-distinct-outcome-with-a-stated-resting-place, scenario: a-refused-answer-is-corrected]

<!-- An answer is bounded, and an over-long one is refused rather than truncated -->
- [ ] AC-5: WHEN an answer's text exceeds the bound THEN it is refused with a reason naming the bound and the length received and no shortened form of it is applied [REQ: an-answer-is-bounded-and-an-over-long-one-is-refused-rather-than-truncated, scenario: the-answer-is-longer-than-the-bound]

<!-- Where the question offered choices, the answer must be one of them -->
- [ ] AC-6: WHEN the question offered a closed set and the answer matches none of it THEN the answer is refused with a reason naming the offered choices and the task remains awaiting [REQ: where-the-question-offered-choices-the-answer-must-be-one-of-them, scenario: an-answer-outside-the-offered-set]
- [ ] AC-7: WHEN the question accepted free text THEN any answer within the length bound is accepted [REQ: where-the-question-offered-choices-the-answer-must-be-one-of-them, scenario: the-question-offered-no-closed-set]

<!-- Every free-text field of an answer document is bounded before it reaches a diagnostic -->
- [ ] AC-8: WHEN an answer document carries a long or control-character-bearing value in a field such as the name of its source THEN what reaches the log is bounded and sanitised [REQ: every-free-text-field-of-an-answer-document-is-bounded-before-it-reaches-a-diagnostic, scenario: a-field-other-than-the-answer-text-carries-hostile-content]
- [ ] AC-9: WHEN the answer document gains a free-text field THEN the enumeration is what decides whether it is bounded, rather than the field being covered by omission [REQ: every-free-text-field-of-an-answer-document-is-bounded-before-it-reaches-a-diagnostic, scenario: a-new-field-is-added-to-the-document]
