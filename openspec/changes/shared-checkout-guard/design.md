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

### D2 — Ownership is recorded from the session's own commands, keyed by `session_id`

The hook sees every Bash command the session runs, and the payload carries `session_id`
(measured: `bin/set-hook-memory:50` already extracts it). On an allowed `git add`, the
hook records the pathspecs the session named. At commit time it compares the index
against that record.

Matching must handle what `git add` actually accepts: an exact path, a **directory**
(which stages everything beneath it), and a glob. So an index path counts as the
session's own if it equals, sits beneath, or fnmatches a recorded pathspec.

*Alternative rejected:* diffing index snapshots. Between two of our observations any
other session may have staged anything, so a snapshot diff cannot attribute the change
to anybody — it would answer a different question than the one being asked.

### D3 — A path another session recorded is foreign, whatever our own patterns say

D2's matching errs toward ownership: a session that ran `git add openspec/` would claim
a path under `openspec/` that a different session staged. So ownership is
**two conditions, not one** — the path matches this session's recorded pathspecs *and*
is not claimed by another session's record. The guard is symmetric: every session's hook
writes its own record, so the common case is covered by the other side's bookkeeping
rather than by guessing.

### D4 — Fail directions, stated separately because they differ

| situation | direction | why |
|---|---|---|
| staged path attributable to nobody observed | **refuse** | an unowned path is exactly the case the guard exists for; assuming it is ours reproduces the bug |
| not a git repository | allow | there is nothing to protect, and erroring here would break unrelated commands |
| command is not a guarded git verb | allow, without reading the index | the hook runs on *every* Bash call; see D5 |
| the guard itself raises | **allow**, and say so on stderr | a crashing guard that blocks every Bash command is worse than the defect it prevents. This is the one place the guard fails open, and it is deliberate rather than accidental |

### D5 — A cheap regex decides before anything expensive happens

The hook is on the `Bash` matcher, so it runs on every shell command in the session. It
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

Following `set-hook-memory`'s `/tmp/set-memory-session-<id>.json`. `/tmp` is the right
store *here* precisely because the state is session-scoped: a session does not survive a
reboot either, so nothing durable is being entrusted to a volatile place. (This is the
opposite call from the agent channel's move off `/tmp`, and for the opposite reason —
that state had to outlive the sessions using it.)

## Risks / Trade-offs

- **The guard fires on a human staging in a terminal** → their paths are unattributable,
  so an agent's pathspec-less commit is refused. That is the correct answer, and the
  message names `git commit -- <paths>`, which costs one flag.
- **A session that stages via something the hook cannot parse** (a script, a wrapper)
  loses attribution for those paths and will be refused → the remedy is the same one
  flag, and the refusal says which paths it could not attribute rather than guessing.
- **`git commit -- <paths>` commits the working tree content of those paths, not the
  index** → a deliberately staged partial hunk (`git add -p`) would be committed whole.
  Rare for an agent; the refusal message should say so rather than let it surprise
  someone.
- **The hook runs on every Bash command** → mitigated by D5, but it is real overhead on a
  hot path and the regex must stay anchored and cheap.
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
