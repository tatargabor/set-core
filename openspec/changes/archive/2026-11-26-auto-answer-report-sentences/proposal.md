## Why

Measured 2026-11-26 21:22, when seven agents asked at once and the owner asked whether automatic
answering was working: two correct proposals were excluded by words in the question that were not
the act asked about — a sentence reporting finished work ("kész és élesben megy (verify PASS,
archive, push)" before "Újraindítsam a watch-ot?") read as `production`, and an approval whose plan
ends "és küldöm a képeket" (pictures back to the operator) read as `send`. Looking for the second
showed a hole in the other direction: the word check is anchored on a word start, so Hungarian
verbal prefixes hid the act — "elküldöm", "kiküldjem", "kitörlöm" matched nothing. Bug register
B-248 (false exclusions) and B-249 (the prefix hole).

## What Changes

- A sentence of the question that reports finished work does not exclude, unless its act is still
  meant (first-person, subjunctive or imperative verb) or the sentence asks.
- A first-person send of pictures, renders or results with no other recipient does not exclude.
- Every exclusion pattern also matches behind a Hungarian verbal prefix (el-, ki-, át-, tovább-,
  vissza-, meg-, le-, fel-, be-, újra-).

## Capabilities

### Modified Capabilities

- `fleet-auto-answer`: the outward-step pattern check.

## Impact

`lib/set_orch/fleet/auto_answer.py` (`_compile`, `_in_report`, `_to_operator`, `exclusion`).
