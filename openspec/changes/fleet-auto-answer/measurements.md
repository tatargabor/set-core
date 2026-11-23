# Measurements — fleet-auto-answer

Aggregates only. The per-question material is the operator's own answers in local transcripts —
consumer data — and stays machine-local (`~/.local/share/set-core/auto-answer-study/`, mode 700).

## S1 — the answer set and the cheap baselines (tasks 0.1, 0.2), 2026-11-23

Source: every `AskUserQuestion` call in `~/.claude/projects/*/*.jsonl` whose result carries the
structured `toolUseResult.answers` (10 448 transcripts scanned; 1201 calls; 102 rejected calls
carry no answer). A call with several questions counts each question.

| measure | count | share |
|---|---|---|
| answered questions | 1544 | — |
| answer is one of the offered options | 1153 | 74 % |
| answer is free text ("Other") | 391 | 26 % |
| questions with an option marked recommended | 1223 | — |
| … of those, the operator picked the recommended option | 832 | 68 % |
| the operator picked the FIRST option | 994 | 64 % |
| answers carrying a note | 11 | — |
| the exclusion pattern fires on question, options or answer | 551 | 35 % (upper bound) |

31 projects; 2026-10: 401, 2026-11: 1138.

What this already says:

- **"Pick the recommended option" is a 68 % answerer.** It is the floor the decider must beat by a
  wide margin; at 68 %, one automatic answer in three would be wrong. Any `likely` bar is set
  against the replay (0.3), never against this number.
- **A quarter of the answers are free text.** On those the operator did not choose — they
  redirected, corrected or added information. A decider that can only pick an option cannot
  produce these; in the replay they count as "not answerable" unless the free text itself is
  written somewhere earlier.
- **Up to a third would be excluded as outward steps.** The pattern is deliberately broad (it
  includes `merge`, `token`, and the ASCII-folded `eles…`, which also matches unrelated words), so
  35 % is an upper bound on the excluded share; the replay measures the real one and the false
  exclusions.

## S2 — replay without time leakage, GLM (task 0.3), 2026-11-23

130 questions sampled stratified (≤ 6 per project, 30 projects, single-question calls only); 13
skipped (6 not a git tree, 7 no commit before the question), 1 unparseable answer → **116
decided**. Model: `glm-5.3-flash` through `set-glm -p`, hooks disabled, no session persisted.
Sources per question, only as they stood before its timestamp: tracked `CLAUDE.md` and
`.claude/rules/*.md` at the last commit before it; a `git grep` keyword search over tracked
markdown at that commit (a proxy for the knowledge base, which cannot be rebuilt for a past
moment); the newest handoff and `MEMORY.md` only if last modified before it; the operator's
earlier answers in the same project (last 25). The user-level instruction file is not versioned
and was left out. Both limits bias the result DOWN.

| measure | n | correct | share |
|---|---|---|---|
| all decisions | 116 | 64 | 55 % |
| baseline: the agent's recommended option | 116 | 59 | 51 % |
| tier `decided` | 21 | 13 | 62 % |
| tier `found` | 8 | 5 | 62 % |
| tier `likely` | 79 | 44 | 56 % |
| … `likely` with confidence ≥ 0.8 | 8 | 5 | — |
| tier `none` (abstained) | 8 | 2 | — |
| **allowed at the proposed bar** (decided, found, likely ≥ 0.8) | 37 | 23 | **62 %** |
| … and not flagged outward | 20 | 12 | 60 % |

Answers by the source class the model named (n, correct): earlier answer 55/29, documentation
search 18/10, rules 12/8, handoff 10/6, open change 6/6, CLAUDE.md 2/2, bug register 2/0, memory
1/0. The model flagged 56 of 116 as outward. Of 29 questions the operator answered with free
text, the model abstained on 2.

What this says, at this model and this retrieval:

- **The allowed tiers are right 62 % of the time** — far under the 90 % the design set as the bar
  for building an automatic writer, and only a little above "take the recommended option" (51 %).
- **The tier label is not trustworthy.** `decided` — "an earlier decision covers it" — was wrong
  in 8 of 21. A tier the model assigns to itself is a claim, not a measurement; it would need a
  check (the quoted excerpt must exist verbatim in the named source) before it could gate
  anything.
- **The model almost never abstains** (2 of 29 free-text answers). It picks an option where the
  operator would have written something else, which is the dangerous direction.
- **Earlier answers carry the most decisions** (55 of 108 answered) but at 53 %; the sources that
  were right every time (open changes, CLAUDE.md) are rare.
- Not separated yet: how much is the model and how much is missing information. The same 116
  replayed with a stronger model separates the two.
