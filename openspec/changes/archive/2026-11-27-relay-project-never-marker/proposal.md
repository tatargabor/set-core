## Why

A project whose agents ask about irreversible live steps (a carrier upload, a label print) needs the
person's own yes in chat for every such call. The decider already excludes outward words, but a taught
rule overrides that exclusion (fleet-relay-teach D5: with `taught=True` only a permission prompt
excludes), and the only extra pattern list, `auto_answer.never_patterns`, is per machine and not in git.
So a project cannot say, in its own committed tree, "these questions are never answered automatically".
Requested over the bus on 2026-11-27 by a consumer project's session (board item
`relay-never-auto-csomag`).

## What Changes

- A project MAY commit `.claude/auto-answer-never.txt`: one regex per line, `#` comments, matched
  case- and accent-insensitively against the question text and every option of every question in a call.
- The literal marker `[no-auto]` anywhere in a question or option is honoured on every machine, with no
  file needed.
- A hit is checked in the worker BEFORE the decider runs: no fork, no lookup, no taught-rule check. The
  whole call is forwarded to the operator unchanged and waits for a human answer. The decision record
  carries the reason (`never auto-answered: <file>:<line>` or `marker [no-auto]`), never the matched text.
- An invalid pattern still excludes what it names: it is matched literally, with a WARNING.

## Capabilities

### Modified Capabilities
- `fleet-auto-answer`: a project-level, committed never-auto-answer rule that outranks a taught rule.

## Impact

- `lib/set_orch/fleet/auto_answer.py` (Layer 1): `never_files(cwd)`, `project_never(cwd)`, `hard_never(questions, cwd)`.
- `lib/set_orch/fleet/auto_answer_worker.py` (Layer 1): `work()` checks `hard_never` before `decide`.
- Tests in `tests/unit/test_auto_answer.py` and `tests/unit/test_auto_answer_worker.py`.
- No consumer tree is written; the file is the project's own.
