# Evidence — the engine driving a real change, in a real tree

Task 8.1 asks for a run whose **product** is recorded, not its exit code. This is that record.
Task 8.2's end-to-end answer path is the middle of the same sequence, because separating them
would have meant asserting per layer, which is what that task forbids.

**Where.** A detached `git worktree` of this repository. That is the honest place for it and
also the point: D3 says the engine is tree-agnostic and the caller supplies the tree, so a
worktree with no orchestration around it is the case that proves it. The framework's own
working tree was never the subject.

**The change under test.** `work-cycle-live-proof`, three groups with **declared
dependencies** (`2` depends on `1`, `3` on `2`) and one task that is deliberately **not the
agent's to decide** — the wording of a line in a file, which the maintainer owns.

## The sequence, and what each step produced

| # | command | verdict | gate | commit | what the tree showed |
|---|---|---|---|---|---|
| 1 | `run` group 1 | `GROUP_DONE` | `no-gate` | `58b9d050` | `NOTE.md` created, one line; verdict and file agree |
| 2 | `run` group 2 | `NEEDS_INPUT` | — | none | second line written, `2.2` marked `- [?]` with its question, unit **set aside** |
| 3 | `status` | — | — | — | `2: awaiting an answer (1 task(s))`, `3: blocked by 2 [declared]` |
| 4 | `answer --task 2.2` | — | — | — | document written under the connector's directory |
| 5 | `status` | — | — | — | `applied …#2.2 (from the surface)`, `2: runnable — selected`; the task is `- [ ]` again |
| 6 | `run` group 2 | `GROUP_DONE` | `no-gate` | `7ee09049` | agent states the decision arrived; `2.2` ticked |
| 7 | `run` group 3 | `GROUP_DONE` | `no-gate` | `92ef9945` | third line = the maintainer's wording, verbatim |

Final: `cat -A docs/work-cycle-proof/NOTE.md` → `group one ran$ / group two ran$ / group three ran$`.
Three commits, **one per unit**. `status` reports all three groups complete and all three runs
finished.

Note what step 2 did *not* do: no commit. A unit set aside for a person does not commit, and
the work stayed in the tree for the next run to build on.

## The part worth more than the green result: two defects this run found

Every unit test in this change passed before this run. Both defects below survived all of them,
and each is an instance of a class this repository already names.

**1. An answer was released but never delivered.** Step 5 — a *reporting-only* invocation —
took the answer in and released the task. By step 6 the answer's **text** was gone, so the
agent asked the same question again, in different words. The release lived in the task file;
the content had nowhere to live.

The unit test that was supposed to cover this ran `answer` then `run` back to back, so the
run's own intake still had the answer in hand. **That is a path the user does not take** —
real use interleaves a look at the state, and intake runs on every path by design, so the
reporting call is *expected* to consume it. The harness had a power the user does not: it
never looked before running.

Fixed by recording an applied answer per change (`set/runtime/work-cycle/<change>/answers.jsonl`)
and carrying it into any later unit whose slice contains that task. Re-run live: the agent's
own verdict says the decision had arrived.

**2. A divergence report stated something untrue.** Step 6's predecessor reported
`claimed complete but not marked in the file: 2.1` — and `2.1` *was* marked, by an earlier run.
The diff subtracted the already-done set from the marked side but not from the claimed side,
so re-claiming earlier work read as an overclaim about the file.

The direction is what makes it expensive: a report that says something checkably false gets
checked once, found wrong, and then ignored — including the times it is right. `TreeDiff` now
has a third category, `claimed_but_done_earlier`, which is an overclaim about *authorship* and
says so.

Both are held by regression tests that drive the user-reachable sequence
(`answer` → `status` → `run`), not the convenient one.

## What this does not prove

- **No gate ran.** The proof project declares none, so `no-gate` is the correct and honest
  outcome — but the gate path itself is exercised only by unit tests here. A project with real
  gate steps is the next thing worth running.
- **The crossing run** on the consuming project's tree (task 8.3) is untouched: it needs the
  other side's participation and their choice of change. It is a human stop, not an omission.
