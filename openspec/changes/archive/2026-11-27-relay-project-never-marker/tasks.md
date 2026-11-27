## 1. The never rule (core, `lib/set_orch/fleet/auto_answer.py`)

- [x] 1.1 `never_files(cwd)`: `.claude/auto-answer-never.txt` of the main checkout and of the call's own tree, deduplicated; shares the root lookup with `taught_files`. [REQ: a-project-can-mark-questions-that-are-never-answered-automatically]
- [x] 1.2 `project_never(cwd)`: `(relative file, line number, pattern)` per non-blank, non-comment line; an unreadable file is a WARNING. [REQ: a-project-can-mark-questions-that-are-never-answered-automatically]
- [x] 1.3 `hard_never(questions, cwd)`: the reason for the first hit (marker first, then patterns in file order) over each question's text and options, folded; invalid regex matched literally with a WARNING; None when nothing hits. [REQ: a-project-can-mark-questions-that-are-never-answered-automatically]

## 2. The worker (`lib/set_orch/fleet/auto_answer_worker.py`)

- [x] 2.1 `work()`: call `hard_never` before `decide`; on a hit build an empty decision, record every question as excluded with the reason, log the label and the reason (no text), and continue on the ordinary forward path. [REQ: a-project-can-mark-questions-that-are-never-answered-automatically]

## 3. Tests

- [x] 3.1 Unit tests for 1.1–1.3: file in the main checkout, comment and blank lines, accent-insensitive match, option hit, marker with no file, invalid regex matched literally, no hit returns None.
- [x] 3.2 Worker test: with a never hit, `decide` is never called, nothing is written, the forward command runs with the question, and the outcome is excluded with the file:line reason, even when a taught rule would allow it. Stash-and-rerun: the test fails without 2.1.

Verified 2026-11-27: `tests/unit/test_auto_answer.py`, `test_auto_answer_worker.py`, `test_relay_teach.py`: 235 passed.
Mutation `never_reason = aa.hard_never(questions, cwd)` → `never_reason = None`: the two worker never-tests fail
(the decider ran), restore asserted by grep, 7/7 pass again.
