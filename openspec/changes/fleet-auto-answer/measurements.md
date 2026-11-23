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
