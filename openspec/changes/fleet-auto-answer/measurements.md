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

## S3 — the conversation as a source, and a stronger model (task 0.4), 2026-11-23

Same 130-question sample and seed as S2; same time cut. New arms: the asking session's
conversation up to the question (operator turns, agent text, earlier answers in the session; last
100 000 characters; nothing after the question), alone or together with the S2 sources. The prompt
asks for the operator's answer from the operator's own words, not the agent's recommendation.
Reference checking (design D8) was NOT applied in this replay — every tier below is still the
model's own claim.

| arm | n | correct | answer was an option: correct | allowed at the bar | allowed, answer was an option | tier `decided` | abstained on free-text answers |
|---|---|---|---|---|---|---|---|
| baseline: recommended option | 116 | 59 (51 %) | — | — | — | — | — |
| A sources, GLM (S2) | 116 | 64 (55 %) | 62/87 | 23/37 (62 %) | 23/29 | 13/21 | 2/29 |
| B conversation, GLM | 116 | 60 (52 %) | 60/87 | 33/60 (55 %) | 33/46 | 16/32 | 0/29 |
| C conversation + sources, GLM | 114 | 68 (60 %) | 67/85 | 38/51 (75 %) | 38/44 | 18/26 | 1/29 |
| **C conversation + sources, Opus** | 116 | **75 (65 %)** | **73/87 (84 %)** | 13/17 (76 %) | 13/15 | 6/7 | 2/29 |

(Two C-GLM calls returned nothing parseable, hence 114.)

What this says:

- **The conversation plus a stronger model is the best arm**, and it is clearly above the
  baseline: 65 % against 51 %, and **84 % on the questions whose real answer was one of the
  options.** Opus was also the most cautious: it put most decisions in `likely` below 0.8, so the
  allowed set is small (17 of 116) and 76 % right; `decided` was right 6 times of 7.
- **The conversation alone does not help a small model** (B, 52 %); with the sources it does (C,
  60 %), and the model matters more than either.
- **The dominant error is not a wrong option, it is a missing abstention.** A quarter of the real
  answers (29 of 116) were free text — the operator redirected or added something — and every arm
  picked an option anyway on 27–29 of them. In the Opus arm 27 of the 41 errors are these. A
  decider that cannot tell "the operator would write something else" will be wrong about one time
  in four on questions like these, whatever its accuracy on the options.
- Not yet measured: the effect of the verbatim reference check (D8) on the tier, and of a prompt
  that rewards abstaining. Both act exactly on the two weaknesses above.

## S4 — the fork, live on this machine (task 2.6), 2026-11-23 23:19–23:22

A scratch interactive session (Claude Code 2.1.331, `--model haiku`, hooks disabled so it took no
bus seat) was started in tmux in a scratchpad folder and given one operator turn: *"I decided:
the release color is TEAL, not orange. Just reply OK"*. While it sat at its prompt, it was forked by
the probe script (`<scratchpad>/fork_probe.py`, not committed) with
`claude -p --resume <id> --fork-session --model haiku --settings '{"disableAllHooks":true}'
--tools Read,Grep,Glob --output-format json`, in its own process group (`start_new_session`), and
the decision prompt on stdin. Measured before and after each fork: the original transcript's line
count, its sha256 and the sha256 of its last line; every `*.jsonl` under `~/.claude/projects/`;
`pgrep -g <pgid>` one second after exit.

| arm | exit | latency | answer | orig transcript | group alive after | new transcript in the session's dir | cache read / total input |
|---|---|---|---|---|---|---|---|
| `--no-session-persistence` | 0 | 2.3 s | TEAL, quote verbatim from the operator turn | 43 lines, sha `b4526259…` → identical | none | **none** | 49 053 / 54 330 (90 %) |
| without it | 0 | 2.5 s | TEAL, same quote | identical | none | **one** (the fork's own id) | 54 328 / 54 330 |

What this settles:

- **`--resume --fork-session` together with `--no-session-persistence` works and leaves nothing
  behind**: no process in the group, no new transcript, the original byte-identical. Without the
  flag the fork's transcript stays on disk (deleted by hand after the probe) — so D12's flag is
  load-bearing, not belt-and-braces.
- **The fork sees the conversation and quotes the operator verbatim**: the quote it returned is
  exactly the operator turn, which is what the reference check (2.5b) will match against.
- **The fork shares the prefix cache**: 90 % of its input was a cache read on the first fork, ~100 %
  on the second. The session here was small (54 k tokens of prefix, mostly the system prompt); the
  share on a long session is a live number for the decision log, not measured here.
- **`--resume <id>` finds the session from any cwd** (a fork run from `/` answered TEAL too), so the
  worker may run in the session's cwd for its read tools without that being what makes resume work.
- **The session's model is in the transcript**: every assistant entry carries `message.model`
  (`claude-haiku-5-5` here) — the fallback source for D8's "the session's own model" when the fleet
  has no provider record.
- Not measured here: whether the fleet's discovery lists a fork while it runs (it lived 2.5 s), and
  a fork of a GLM session through its wrapper.
