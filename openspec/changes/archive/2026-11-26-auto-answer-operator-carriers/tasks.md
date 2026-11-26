## 1. The check

- [x] 1.1 `operator_turns` reads typed prompts, human-origin queued commands, dialog answers (both runtime wordings) and the relay continuation instruction; drops peer and subagent messages
- [x] 1.2 `own_written_answers` from the decision log; `operator_turns(..., exclude)` drops them; `decide` passes them (injectable for tests)
- [x] 1.3 `quote_in`: folded substring, then a word-for-word match with bounded typos; short words exact
- [x] 1.4 Tests for every carrier, every non-operator carrier, the own-write exclusion and the matcher (26 fail without the fix, stash-and-rerun)
- [x] 1.5 Replay over every recorded operator quote: 23 refused → checked, 0 checked → refused (B-245 entry)

## Acceptance

- [x] AC-1: WHEN the operator typed the decision while the agent worked THEN the quote checks and the tier is `decided` [REQ: the-decision-names-its-tier-and-its-source, scenario: a-quote-the-operator-typed-while-the-agent-worked]
- [x] AC-2: WHEN the quoted words are what the automatic answer wrote THEN the quote does not check [REQ: the-decision-names-its-tier-and-its-source, scenario: the-automatic-answer-s-own-words-are-not-evidence]
- [x] AC-3: WHEN the fork corrects the operator's typos THEN the quote checks, and WHEN it adds or drops a negation THEN it does not [REQ: the-decision-names-its-tier-and-its-source, scenario: a-quote-with-the-operator-s-typos-corrected]
