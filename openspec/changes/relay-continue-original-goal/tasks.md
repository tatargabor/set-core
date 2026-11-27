## 1. Goal source

- [x] 1.1 `opening_prompt(path)`: the first user entry with the user's own text, from the transcript head (≤ 400 lines), skipping tool results, command/local-command wrappers, caveats and task notifications; bounded to 800 chars; None on any read error [REQ: the-continuation-post-names-the-session-s-original-goal]
- [x] 1.2 Suggester prompt takes the opening prompt and asks for an optional `GOAL:` line; `parse_goal` reads it (≤ 200 chars) [REQ: the-continuation-post-names-the-session-s-original-goal]

## 2. Post and wake

- [x] 2.1 `continuation_question` shows `Started for: <goal>` and the "still holds?" question, or the no-goal variant [REQ: the-continuation-post-names-the-session-s-original-goal]
- [x] 2.2 The fixed `→ Keep going toward the original goal` option first, then at most three suggestions [REQ: the-continuation-offers-keeping-going-toward-the-goal]
- [x] 2.3 `instruction()` expands the fixed option into the re-check-then-continue instruction, keeping the auto-answer writer note [REQ: the-continuation-offers-keeping-going-toward-the-goal]

## 3. Tests

- [x] 3.1 Opening prompt: wrappers and tool results skipped; bound; unreadable file → None [REQ: the-continuation-post-names-the-session-s-original-goal]
- [x] 3.2 Post text with and without a goal; options order; nothing logged with prompt or goal text [REQ: the-continuation-post-names-the-session-s-original-goal]
- [x] 3.3 Wake instruction for the fixed option, by the owner and by the auto-answer [REQ: the-continuation-offers-keeping-going-toward-the-goal]
- [x] 3.4 Prove the new tests fail on the old module, then run the relay suites [REQ: the-continuation-offers-keeping-going-toward-the-goal]

## 4. Acceptance

- [ ] 4.1 Live: a finished session's post on the real channel shows the goal and the keep-going option, and picking it wakes the session, which re-checks its goal [REQ: the-continuation-offers-keeping-going-toward-the-goal]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the suggester returns a GOAL line THEN the post shows `Started for:` and asks whether it still holds [REQ: the-continuation-post-names-the-session-s-original-goal, scenario: a-goal-is-shown]
- [x] AC-2: WHEN no GOAL line is returned THEN no `Started for:` line and the post still asks whether anything is left [REQ: the-continuation-post-names-the-session-s-original-goal, scenario: no-goal-returned]
- [x] AC-3: WHEN the transcript starts with a wrapper and a tool result THEN the first own text is the opening prompt [REQ: the-continuation-post-names-the-session-s-original-goal, scenario: the-opening-prompt-skips-tool-results-and-wrappers]
- [x] AC-4: WHEN a continuation has two suggestions THEN the options are the fixed keep-going option then the two [REQ: the-continuation-offers-keeping-going-toward-the-goal, scenario: the-fixed-option-comes-first]
- [x] AC-5: WHEN the owner answers keep going THEN the wake instruction re-checks the goal and continues or says why and stops [REQ: the-continuation-offers-keeping-going-toward-the-goal, scenario: picking-keep-going]
- [x] AC-6: WHEN the auto-answer writes keep going THEN the instruction names the auto-answer as the writer [REQ: the-continuation-offers-keeping-going-toward-the-goal, scenario: an-auto-written-keep-going-names-its-writer]
