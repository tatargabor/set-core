## Context

The question relay holds an agent's blocking point (a question, a finished turn's "what next?", a
permission prompt) and hands it to the operator's channel. The auto-answer decider
(`fleet-auto-answer`) looks at each relayed call first. It writes an answer only when the answer is
decided or found, and otherwise forwards the call with its verdict. The fleet header's relay panel
lists the waiting calls with that verdict in one line.

Two gaps showed on the first live day:
- **The operator cannot read the question on the panel.** The decider's pending record holds the
  text, but the panel does not show it.
- **Nothing learns.** An abstention today is an abstention tomorrow on the same question, because the
  only ways to give the decider a rule were editing a machine-local config key
  (`auto_answer.standing`, a pointer to a Markdown section) or writing into a project's instruction
  files by hand.

## Goals / Non-Goals

**Goals:**
- Read any waiting call in full without leaving the fleet.
- Teach a project-level rule in one save that also answers the call in front of you.
- Let the rule reach the decider AND every agent of that project, on every machine that has the
  project checked out.

**Non-Goals:**
- Editing or removing rules from the screen: the file is plain Markdown in the project.
- Rules that span projects.
- Any path that answers a permission prompt.
- Pushing.

## Decisions

### D1 — The rules live in `.claude/rules/auto-answer-taught.md` of the project
The owner asked for project-level rules that are committed, so a teammate works the same way. A
file under `.claude/rules/` is loaded by every Claude Code session in that project, which gives a
second effect for free: **an agent that has the rule in its instructions stops asking**. The
decider already treats `.claude/rules/` as a decision location, so a verbatim quote from it checks
as `decided` with no new mechanism.
- *Rejected:* a machine-local store under `~/.config/set-core/`. A teammate would not have it, which
  is the owner's stated requirement.
- *Rejected:* `docs/decisions/`. The agents do not load it, so they keep asking and only the decider
  learns.
- `set-project init` does not manage this path; it is not in the deploy manifest, so a redeploy
  cannot overwrite it.

### D2 — The main checkout, not the asking worktree
The rule goes into the main worktree: the first entry of `git worktree list --porcelain` for the
repository holding the call's `cwd`. A rule committed on a worktree's feature branch would reach
the rest of the project only when that branch merges, and it would vanish if the branch were
dropped. The main worktree is where a teammate's pull lands. The commit goes on the branch checked
out there, and the result names that branch. On a detached HEAD the file is written but not
committed, and the result says why: a commit there would be unreachable.

### D3 — One path, committed alone, hooks running, never pushed
The file is added with `git add -- <file>` and committed with `git commit -m <msg> -- <file>`. A
pathspec commit takes only that path and leaves the rest of the index as it was. Another agent may
have staged work in the same checkout, and the repository's own rule names that sweep as a measured
hazard.
- The message is generic (`auto-answer: taught rule <date>`). The rule's text stays out of the
  message, so a public repository's message scan has nothing new to read.
- The project's hooks run (no `--no-verify`), leakscan included. A refusal is reported, not bypassed.
- An `index.lock` held by another process is retried briefly, then reported.
- No push: the owner asked to commit. The project's own push publishes it with the rest of its
  work, and a push from here could publish another agent's unfinished commits on that branch.

### D4 — Answer first, then write
Saving delivers the answer through `question_relay.deliver_answer` first, the same path as the
panel's send button, because an agent waiting is the cost being paid. The rule is written and
committed after that. Each step reports on its own. Neither undoes the other: an answered call with
an uncommitted rule, or a committed rule for a call that had already ended, are both true states
and the overlay shows them.

### D5 — The decider gets the rules verbatim, and a rule-backed answer is not excluded
The taught file is read from the main checkout (and from the call's own tree when different) and
placed in the prompt like the standing decisions: verbatim, labelled, with the instruction to
apply a rule only when its stated condition holds. This repeats the lesson of `fleet-auto-answer`'s
live morning: a pointer to a file was not used, the verbatim text was.

The exclusion exception is deterministic. The worker passes `taught=True` to `exclusion()` when one
of the answer's references is a CHECKED decision quote whose path is a taught-rules file. Only a
permission prompt still excludes then. The owner chose this (*„Mindig mehet"*). The model's own
outward flag is overridden too, because a taught rule is the operator's answer given in advance.
The decision log records `taught: true` on such a record, so every write that went through a rule
over an outward word can be counted afterwards.

### D6 — Details reads the decider's record; the relay's own record is the fallback
`GET /api/fleet/question-relay/{call_id}/detail` returns the pending record of that call: questions,
options, choice, tier, outcome, reason and checked references. Beside it come the waiting record's
kind, age, question count and release flag. With no pending record the response says so. It reads
machine-local stores only. The route is served on localhost like the rest of the fleet API, and it
logs shape only.

### D7 — Two text controls in the row, overlays over the panel
"details" and "teach" sit beside "to terminal ↩". Each opens an absolutely positioned overlay above
the relay panel with its own close control, so nothing in the panel moves (the repository's overlay
rule). The teach result stays until closed when anything failed. When everything succeeded it
closes after 10 s, the repository's figure for a finished event.

## Risks / Trade-offs

- **A taught rule can approve a production step on the model's reading of a condition.** The
  owner's explicit choice. It is bounded three ways: the reference must be a checked verbatim quote
  of the rule, the decision log counts these writes, and the rule is a plain file in the project
  that anyone can read and correct.
- **Every session of the project loads the file.** It costs context per rule. The decider caps what
  it reads (20 KB, the newest entries kept, with a WARNING when cut). A file that grows past that is
  a sign to consolidate it by hand.
- **The commit lands on whatever branch the main checkout has.** If that is a long-lived feature
  branch, the rule waits for its merge. The result names the branch so this is visible.
- **set-core writes into another project's tree.** It writes only on the operator's click, only one
  file under `.claude/rules/`, and only through the project's own hooks.

## Migration Plan

Nothing to migrate: a project without the file behaves as today. Rollback is deleting the file in
the project, or reverting its commits.

## Open Questions

None blocking. Editing and removing rules from the screen is deliberately left to the file.
