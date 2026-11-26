## 1. The pattern check

- [x] 1.1 `_in_report`: a report sentence's act does not exclude unless still meant or asked
- [x] 1.2 `_to_operator`: a first-person send of pictures/renders/results with no recipient does not exclude
- [x] 1.3 `_HU_PREFIX` in `_compile`: verbal prefixes no longer hide an act
- [x] 1.4 Tests: 4 pass cases from the live log, 6 controls that must still exclude
- [x] 1.5 Replay: 125 recorded proposals, old vs new — 4 flips, all to "not excluded", each read and right (two report sentences about live status, the watch restart, the pictures); the prefix rule over the words of the decision log and 400 transcripts' user turns adds only real acts (kiküldése, elküldte, kitörölni, befizetés, …)

## Acceptance

- [x] AC-1: WHEN a report sentence of finished work precedes the question THEN it does not exclude [REQ: outward-and-irreversible-steps-are-never-answered-automatically, scenario: a-report-of-finished-work-beside-the-question]
- [x] AC-2: WHEN the plan ends with pictures sent back to the operator THEN it does not exclude [REQ: outward-and-irreversible-steps-are-never-answered-automatically, scenario: pictures-sent-back-to-the-operator]
- [x] AC-3: WHEN the act is behind a verbal prefix THEN it still excludes [REQ: outward-and-irreversible-steps-are-never-answered-automatically, scenario: a-verbal-prefix-does-not-hide-the-act]
