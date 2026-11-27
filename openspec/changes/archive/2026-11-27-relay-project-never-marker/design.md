## Context

`auto_answer_worker.work()` is the only path that writes an automatic answer (measured 2026-11-27: the
only `decide(` call and the only `_write_answer(` call outside tests are in that function). The decider's
exclusion is applied per chosen answer, after the decision, and `taught=True` returns before any pattern.

## Decisions

### D1 Checked before the decider, for the whole call

A never-hit is checked on the question text and every option of every question in the call, before
`decide` runs. Why before: a rule that outranks a taught rule must not depend on what the model chose or
which reference it quoted, and a call that can never be written costs no fork. Why the whole call: the
worker is already all-or-nothing per call (a call is answered by one party), so one hit forwards all.

### D2 The file lives where the taught rules live

`.claude/auto-answer-never.txt` is read from the repository's main checkout and from the call's own tree
when that is a different worktree, the same roots `taught_files` uses, so a rule committed on main also
binds a worktree session. It is a plain list, not a rules `.md`, because it is parsed, not read by agents.

### D3 The marker needs no file

`[no-auto]` is a built-in pattern. A skill that asks about a live step can put it in the question and be
safe on a machine where the project file is missing or the checkout is stale.

### D4 Patterns are regexes on folded text, unanchored

Folded the same way as the outward families (lower case, accents removed), pattern folded too, searched
anywhere. Unlike the families, no word anchor is added: the project writes the exact regex it means, and
the marker contains brackets. An invalid regex is matched literally (the `never_patterns` rule: a broken
pattern still excludes what it names).

### D5 The reason names the rule, never the text

`never auto-answered: .claude/auto-answer-never.txt:<line>` or `never auto-answered: marker [no-auto]`.
The question text can carry a client's data; the log and the decision record already store the question
separately under the existing log rules, and the reason adds nothing to it.

## Risks

- A pattern that is too broad stops automatic answers for that project entirely. That is the fail-safe
  direction (the person is asked), and the reason names the line to fix.
