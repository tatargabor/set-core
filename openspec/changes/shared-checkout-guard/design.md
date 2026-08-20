## Context

Several Claude sessions work in `/home/tg/code2/set-core` at once. That is ordinary
here, not an edge case — three threads were active in it on 2026-08-20. A checkout has
**one index and one working tree**, so a command that names no paths acts on all of it,
including whatever another session is holding.

Measured that day (bug **B-32**), in a throwaway repo, so the mechanism is not inferred
from the incident:

| command run by session A | what it took from session B |
|---|---|
| `git add -A` | B's untracked and modified files |
| `git commit` (no pathspec) | B's **staged** paths — even though B staged only its own |
| `git stash` (no pathspec) | B's files **removed from the working tree**; B's `git status` went clean |
| `git commit -- <A's paths>` | **nothing** — B's staged entry survived in the index |

The last row is the cure and it is already available; nothing needs inventing. What is
missing is that nothing enforces it. `.claude/rules/cross-cutting-checklist.md` has said
"list paths explicitly" since before the incident, and the session that lost its commit
had followed it exactly — because the rule only covers `git add`, and the loss happened
at `git commit`.

`set-hook-leakscan` already occupies the `PreToolUse` / `Bash` slot and documents why
that slot exists: *an instruction is not a constraint; what an agent cannot do is decided
by the tools it holds.* This change adds the second occupant of that slot.

## Goals / Non-Goals

**Goals:**
- An agent cannot produce a commit carrying a path another session staged.
- An agent cannot sweep with `git add -A` / `.` / bare `-u`, or `git commit -a`.
- An agent cannot `git stash` another session's work out of the working tree.
- The refusal names the offending paths and the exact command to run instead.
- Silence when the session is alone with its own work — including in a worktree.

**Non-Goals:**
- Deciding who *should* own a path, or merging two sessions' intentions.
- Anything about `git push` / `git tag`; that is `set-leakscan`'s question.
- Repairing an incident after the fact. Amending or rebasing another thread's commit
  takes back what it is holding right now, which this repository has already ruled is
  more expensive than a badly grouped commit.
- Deploying the guard to consumer projects in this change — see Open Questions.

## Decisions

### D1 — Guard the COMMIT, not only the ADD

The obvious guard is on `git add -A`, and it is insufficient. In the measured incident
the other thread could have staged its own directory perfectly legitimately
(`git add openspec/changes/fleet-pm-mode/`) and its pathspec-less commit would still have
carried the eight foreign paths. The index is the shared object; the commit is where it
gets published. *Alternative rejected:* guard only the sweeping forms — it leaves the
path that actually caused the loss wide open.

### D2 — Ownership is MEASURED from the index, never parsed from the command

The hook runs on both `PreToolUse` and `PostToolUse` for the `Bash` matcher — the
`PostToolUse` / `Bash` slot already exists and is occupied by `set-hook-memory`. Around a
staging command the guard takes two snapshots of `git diff --cached --name-only`: one
before it runs, one after. **The difference is what that command staged**, and it is
therefore that session's own.

The point is that nothing reads the command's arguments. A pathspec can reach `git add`
in at least six forms this repository actually uses — a shell glob the hook only sees
unexpanded, a variable, `xargs git add`, `git -C <dir> add`,
`--pathspec-from-file`, and a script that stages on the session's behalf. Every one of
them defeats argument parsing, and each defeat produces an *unattributable* path, which
the guard must treat as foreign. So the parsing design does not fail loudly: it degrades,
one command at a time, into "every commit needs a pathspec" — which is the shape that was
explicitly not chosen.

Measuring the effect instead of reading the intent is the same discipline this repository
already states for checks in general: *the mechanism running is not the result*. Here the
result — which paths entered the index — is directly observable and costs one command.

*Alternative rejected:* parsing `git add` pathspecs and matching index paths against them
by equality, directory prefix and fnmatch. It needs all three rules to approximate what
git does natively, it over-claims (a session that ran `git add openspec/` would swallow a
neighbour's file under that directory, which then needed a whole second condition to undo),
and it still loses to all six forms above.

*Alternative rejected:* snapshot-diffing without pairing the snapshots to one command.
Between two unpaired observations any session may have staged anything, so the diff cannot
be attributed to anybody — it answers a different question than the one being asked. The
pairing to a single tool call is what makes the delta mean something.

### D3 — A staging step and a pathspec-less commit in ONE command are refused, and that is correct

`git add x && git commit` arrives as a single Bash call, so the guard's `PreToolUse` runs
before the `add` has happened: the session's own path is not in the index yet and the
commit would be judged against an index it does not yet own. Rather than reach back for
argument parsing to special-case this, the guard refuses it — and the refusal is
actionable without changing the shape of the command, because the remedy composes:
`git add x && git commit -- x`.

*Alternative rejected:* splitting the command and simulating each part. That is parsing
again, with the extra hazard of the guard modelling a shell.

### D4 — Fail directions, stated separately because they differ

| situation | direction | why |
|---|---|---|
| a staged path that entered the index outside any observed command of this session | **refuse** | an unowned path is exactly the case the guard exists for; assuming it is ours reproduces the bug |
| not a git repository | allow | there is nothing to protect, and erroring here would break unrelated commands |
| command is not a guarded git verb | allow, without reading the index | the hook runs on *every* Bash call; see D5 |
| the guard itself raises | **allow**, and say so on stderr | a crashing guard that blocks every Bash command is worse than the defect it prevents. This is the one place the guard fails open, and it is deliberate rather than accidental |

### D5 — A cheap regex decides before anything expensive happens, on BOTH events

The hook is on the `Bash` matcher for both events, so it runs twice per shell command. It
matches a guarded git verb with one compiled regex and exits 0 immediately otherwise —
no subprocess, no index read. Only a matching command pays for `git diff --cached
--name-only`.

### D6 — Reuse leakscan's two solved problems rather than re-solving them

`set-hook-leakscan` already strips **heredoc bodies** before matching (otherwise the hook
fires on a command that merely *writes about* the verb — measured there: writing that
hook's own tests was blocked by it), and already resolves a `cd` inside the command to
find the real target repository. Both apply here identically and are lifted, not
reinvented.

### D7 — Session state lives in `/tmp`, keyed by session id

Following `set-hook-memory`'s `/tmp/set-memory-session-<id>.json`. It holds two things: the set of paths this session is known to have staged, and one pending pre-snapshot slot. A single slot is enough because a session's Bash calls are sequential, so at most one staging command is ever in flight. `/tmp` is the right
store *here* precisely because the state is session-scoped: a session does not survive a
reboot either, so nothing durable is being entrusted to a volatile place. (This is the
opposite call from the agent channel's move off `/tmp`, and for the opposite reason —
that state had to outlive the sessions using it.)

## Risks / Trade-offs

- **The guard fires on a human staging in a terminal** → their paths are unattributable,
  so an agent's pathspec-less commit is refused. That is the correct answer, and the
  message names `git commit -- <paths>`, which costs one flag.
- **A race inside one command.** If another session stages between this session's
  pre-snapshot and post-snapshot, the delta credits that path to the wrong session, and a
  foreign path is then treated as owned. The window is the duration of one `git add`, which
  is the narrowest this design can make it — but it is not zero, and it fails in the
  *permissive* direction. Say so in the code where the delta is computed, rather than
  leaving a reader to assume the attribution is exact.
- **A staging step and a commit in one Bash call are refused** (D3) → the remedy composes
  into the same command (`git add x && git commit -- x`), but it will surprise someone the
  first time, so the refusal must name that exact rewrite rather than the generic one.
- **`git commit -- <paths>` commits the working tree content of those paths, not the
  index** → a deliberately staged partial hunk (`git add -p`) would be committed whole.
  Rare for an agent; the refusal message should say so rather than let it surprise
  someone.
- **The hook now runs twice per Bash command** (pre and post) → mitigated by D5's
  regex-first exit, but the hot path just doubled and the regex must stay anchored and cheap.
- **A session that unstages and a neighbour then stages the same path** → this session's
  record still claims it. Subtract removals from the record as well as adding arrivals,
  or the claim outlives the fact.
- **The guard fails open on its own exception (D4)** → a silently broken guard is
  indistinguishable from a guard with nothing to report. Its stderr note is the only tell,
  so the tests must include one that proves the guard actually refuses, rather than only
  tests that prove it allows.

## Migration Plan

1. Ship `bin/set-hook-checkout-guard` and its tests.
2. Register it in `.claude/settings.json` beside `set-hook-leakscan`.
3. Amend `.claude/rules/cross-cutting-checklist.md` with the missing half — the pathspec
   belongs on the **commit**, in addition to the `add`, not instead of it.
4. Close **B-32** in the register with the commit sha, per the register's own rule that
   entries are closed with evidence and never deleted.

Rollback is removing the one `.claude/settings.json` entry; nothing else changes state.

## Open Questions

- **Should this deploy to consumer projects?** Their orchestration agents run in
  worktrees and are therefore immune (measured), but their main checkouts are shared the
  same way this one is. Not measured there, so it is not claimed here — decide it as its
  own step rather than folding an unmeasured surface into this change.
- **Does anything legitimately need a pathspec-less `git stash` in this tree?** If the
  answer turns out to be yes, the refusal needs a documented way through that is not
  "disable the hook".
