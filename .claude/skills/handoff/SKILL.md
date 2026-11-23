---
name: handoff
description: Session handoff — writes one thread's open work, MEASURED state and next step into an ID-tagged file, so a compact or /clear cannot dilute it. Use before switching sessions, when the budget runs low, or when a compact is coming. The successor loads it with `/handoff <ID>`.
user_invocable: true
---

# handoff — hand one work thread to a successor with a clean context

**The goal:** make `/clear` + a fresh session cheaper and cleaner than a compact — which it
only is if the state is **written down**, not held in the context.

**Why this exists (measured in the project this skill was extracted from):** over two days,
**62 forced compacts**; **69% of the token budget** went into re-reading accumulated context
rather than into the work.

---

## The model — stated explicitly

**A handoff is not a repo artifact, it is a message between sessions.** Therefore:

| | |
|---|---|
| where | `.set/handoff/<ID>--<slug>.md` — **gitignored**, never committed |
| ID | `<MMDD>-<4 hex>`, e.g. `0726-3f9a` — writing it **prints the ID**; that is what the successor gets |
| loading | **by hand only**: `/handoff <ID>`. No SessionStart auto-injection |
| end of life | a manual `rm`, or it just sits there — nothing references it |

**One thread = one file = one writer.** Parallel sessions on one working tree are normal
(measured: five at once). A single shared file is structurally wrong — whoever writes second
silently overwrites the first. A separate ID means no race, and no lockfile.

**Why not auto-injected into every session:** if every session gets everything, nobody *carries*
the thread, and you then need collision signalling, staleness measurement and archiving — an
apparatus whose only cause is that the file outlives the read. Loading by ID makes all of it moot.

---

## The project profile — where the project-specific part lives

This skill is deliberately generic. What "state" means differs per repo: a green test suite in
one, which client document has been generated and sent in another.

**Read `.claude/handoff.profile.md` if it exists.** It carries, written by the project:

- **What "state" means here** — one paragraph
- **Probes** — the commands worth running in this repo, with what each tells you
- **Never lose** — runtime scratch, untracked drafts, anything gitignored that would vanish silently
- **Parallel sessions** — which paths belong to other threads
- **Template extras** — optional: extra columns/sections for the skeleton below

⚠ **If there is no profile, say so in the handoff** ("no project profile — only the universal
probes were run"). Silence would let the successor read a thin measurement as a simple project.
Offer to create one from `templates/handoff.profile.md` in this package.

---

## `/handoff` — writing (no arguments)

### Phase 1 — MEASURE, do not recall

⚠ **Not skippable, and not replaceable by recalling the conversation.** The date, the commit
SHA, the count are fields you fill in "roughly" because the sentence *formally requires* them —
that is exactly the class of error that gets into a handoff, and the successor **cannot check it**.

Universal, run these always:

```bash
date '+%Y-%m-%dT%H:%M:%S%:z'    # the header timestamp — NEVER from memory
git rev-parse --abbrev-ref HEAD # which branch we are on
git log --oneline -8            # where the tree is
git status --short              # uncommitted AND untracked work
```

Then the probes from `.claude/handoff.profile.md` — only the ones relevant to this thread; do
not run all of them blindly.

**Do not claim what you did not measure.** If a number is missing, write *"not measured"*. That
is always cheaper than a plausible but false number the successor takes at face value.

### Phase 1b — THE OTHER CARRIERS: what else outlives this session

⚠ **The handoff is not the only thing that survives.** A session also leaves behind persistent
memory, gitignored scratch, and background processes — and the successor meets **those first**,
because a handoff has to be loaded by hand while memory is injected automatically. **A wrong
memory is therefore more dangerous than a wrong handoff.**

Measured, in the session this section was added from: a memory written in the first hour said the
key data source was one subsystem and that a certain kind of write was impossible. Both were
disproven **the same day**, by this same session. Nobody would have caught it — the handoff was
correct, and the successor would have started from the memory.

So before writing the handoff, go through what this session wrote to any persistent carrier:

```bash
# persistent memory — did THIS session write or change any of it?
ls -lt <memory-dir>/*.md 2>/dev/null | head        # e.g. ~/.claude/projects/<slug>/memory/
# anything gitignored that would vanish: scratch dirs, run state, drafts
git status --short --ignored 2>/dev/null | grep '^!!' | head
# background processes this session started and did not stop
ps -eo pid,etime,args --no-headers | grep "[m]y-probe-pattern"
```

For each memory this session wrote: **is it still true after everything measured since?** If not,
**fix it now, in the same breath** — and say in the handoff that you did, including what was wrong.
A corrected memory that hides its own correction invites the next session to re-derive the error.

Then record in the handoff, under §4:

- which memory entries this session wrote or corrected, and **why** the correction was needed;
- which files exist only in scratch — see the rescue rule below;
- any background process still running, or an explicit "none left".

Do **not** silently reach for a wholesale cleanup here — see the warning in Phase 3.

#### Scratch that is expensive to rebuild must be RESCUED, not merely named

The list above says "name the scratch files". That is not enough, and the gap is measured: a
session produced 3 400 lines of extracted, cross-checked data in the scratchpad — hours of
subagent work — and the handoff dutifully *named* the directory. The scratchpad dies with the
session. Naming it hands the successor a receipt for something already gone.

So apply a cost test to every scratch artifact, and act on the answer:

| rebuild cost | what to do |
|---|---|
| one command, seconds | name it and the command that regenerates it — that is enough |
| minutes of scripted work | name it, and paste the exact command into §0 |
| **subagent runs, API calls, or anything measured in hours** | **copy it somewhere that survives** — a gitignored directory inside the repo, or an explicitly named path outside the scratchpad — and say in §4 where it went |

The rescue is two lines of `cp`. Skipping it is the one loss in this whole document that
**cannot be undone by the successor at any price**: a commit can be reverted, a memory can be
corrected, a wrong number can be re-measured — but a deleted scratch tree that cost three hours
of agent time is simply gone.

#### Harness-tracked work is a carrier too — and it is invisible to `ps`

A background Workflow, a queued task, a long-running tool call: none of these show up in
`ps` under a name you can grep, and none of them survive the session — but several of them
**can be resumed** if, and only if, their identifiers were written down.

Record, for anything launched this session that is still running or finished within it:

- the **run/task id** and the **script or transcript path** (a workflow can be resumed with
  `{scriptPath, resumeFromRunId}`; without both, the cached agent results are unreachable);
- whether it **finished, is still running, or was abandoned** — and if it was still running when
  the handoff was written, say so plainly, and say where its output will land;
- what it was *for*, in one line, so the successor can decide whether resuming is even wanted.

The failure this prevents: the successor sees the output files, cannot tell whether the run
completed, and re-runs the whole thing — paying the full cost a second time to learn something
the previous session already knew.

#### Anything published outward carries a URL, and the URL is the artifact

If this session published, deployed, or shared anything that lives at an address — a published
page, a PR, an issue, a document in a connected service — **the address goes in the handoff**.

This is not bookkeeping. A successor who cannot find the URL does not fail loudly: it publishes
a *second* one. Now two versions exist, the link already given to other people points at the
stale one, and nothing anywhere reports a conflict. Write the URL, and write what it contains.

#### If the session joined a channel, the successor is a different participant

Where sessions talk to each other (a message bus, a shared room, a queue), identity is usually
**per session**, not per project — so the successor arrives as a *new* participant. It will not
inherit the unread mail, and the other side will not know the seat changed.

Record: which room or channel, under what name this session appeared, whether anything was left
unanswered, and who is waiting on a reply.

### Phase 2 — ID and file

If this session **was loaded with `/handoff <ID>`**, reuse **that same ID** — a thread's ID is
stable along the whole chain. Otherwise generate one:

```bash
mkdir -p .set/handoff
ID="$(date +%m%d)-$(openssl rand -hex 2)"    # e.g. 0726-3f9a — NEVER from memory
echo "$ID"
```

The file: `.set/handoff/$ID--<slug>.md` (`<slug>` = the thread's name in kebab-case, only so
`ls` reads well; loading needs the ID alone). Use **exactly** these sections — keep an empty
section with a "none" marker too, because a missing section and missing content look identical
from the outside:

**Write the file with the Write or Edit tool — never with Bash** (`cat > … <<EOF`, `cp`, `sed -i`,
`tee`). The hooks that act on a handoff (its content check, and under auto-clear the marker that
arms this session for an automatic `/clear`) are PostToolUse hooks on Write/Edit. A shell write
passes them by in silence: measured 2026-09-21, a sheet written with a heredoc left its session
unarmed, and the watcher refused to clear it every minute while the session sat at "Ready for
/clear". The shell is fine for READING the previous version, never for writing this one.

```markdown
# HANDOFF: <slug> — <ISO date from the `date` command>   ·   ID: <ID>

> **The conversation is not a source.** Whatever is not written here is lost at the next compact.
> Under every number, the command that produced it.

**In one sentence:** <where THIS thread stands and what the next step is>

**This thread's goal:** <what THIS session is for — the goal/plan item it serves, or "own
 thread". A project-level goal/plan file is context for the successor, not its work queue; the
 lanes other sessions own go into §6.>

---

## 0. Start here — probe commands

<what the successor can MEASURE the state with, rather than believe it. For each: what you expect.>

## 1. Open work — EVERY thread on this line

<Itemised. NOT only the one I happened to be working on.>

| # | thread | state | where the trace is |
|---|---|---|---|

## 2. What was decided (and where it is written)

<Decision → the repo file that carries it. If it was decided only in the conversation and is
 written nowhere, then it was NOT decided — either write it down now, or move it to §1.>

## 3. What is blocked — DECISION or WORK

<Separated. "Waiting on a user decision" and "agent work remains" are different things,
 and the successor handles them differently.>

## 4. What this round measured / changed

<With commit SHAs (from `git log`) and measured numbers.>

<Then, from Phase 1b — the carriers OTHER than this file:
 · memory written or corrected by this session, and why;
 · files that live only in scratch and will die with it;
 · background processes still running, or "none left".
 If none of the three applies, say so — a missing section and an empty one look identical.>

## 5. Next steps, in order

1. …

## 6. What NOT to touch

<If another session works in parallel: which files/directories are theirs.
 If none: "no parallel thread".>

## 7. What we learned about the METHOD

<Only what would change HOW the successor works — not what it should work on.
 A technique that turned out not to pay for itself; an ordering that should have been
 the other way round; a check that caught something nothing else would have.
 Each with the measurement that showed it. If nothing: "nothing methodological".>
```

If the profile has a **Template extras** section, apply it here — an extra column, an extra
warning line, an extra section. Do not drop any of the sections above for it.

### Phase 3 — uncommitted work

The handoff file itself does **not** go into git. But if `git status` showed uncommitted or
untracked work, **say so in the handoff** — otherwise the successor does not know there is
something to save.

⚠ **Cleanup must NEVER be `git reset --hard`** while there is uncommitted work in the tree: it
takes your own unsaved edits with it (measured: it removed two finished, uncommitted files during
this very skill's development). For a targeted revert use `git restore -- <path>`; to drop a
temporary commit, `git reset --soft`. On untracked files `git clean` is forbidden the same way.

### Phase 4 — report to the user

**Lead with the ID** — without it the successor cannot find the file:

```
Handoff written: .set/handoff/0726-3f9a--session-budget.md
→ in the new session:  /handoff 0726-3f9a

2 open threads, 1 waiting on a user decision. Ready for /clear.
```

`/clear` is issued **by the user** — or by the session's own automation, when the gates hold (handoff written for THIS session, context past the threshold, idle, no pending prompt; an external executor types it — see `templates/clear-gate.mjs` and `templates/selftest-clear-reload.sh` in the package). Never by your own tools: no session has a tool to erase its own context.

### Phase 4b — make it visible to the fleet

**The handoff file is gitignored and machine-local by design — which means an orchestration
layer (a fleet view, a registry, another machine) has NO trace of it.** Measured 2026-09-12:
the fleet view of the coordinating session showed nothing about a written handoff, because it
reads the agent-comm store (registry, focus, beats) and tracked repo files — and the handoff
lives in a gitignored directory with a trace in neither.

So if the session has the agent-comm `focus` tool, **announce the handoff on focus** as the
last step of writing (and of loading):

- after writing: focus text `handoff <ID> written — <slug>; successor loads it with /handoff <ID>`
- after loading: focus text `handoff <ID> loaded — continuing <slug>`

The focus is what a fleet view already renders for the seat, so the handoff becomes visible
there with zero new infrastructure. Where the tool does not exist, this step is a no-op —
skip it silently. Do NOT commit the handoff to make it visible: the file stays local (a
message between sessions, not a repo artifact); the POINTER travels, not the file.

---

## `/handoff <ID>` — loading

```bash
ls .set/handoff/<ID>--*.md
```

**The loaded thread is your work — nothing else.** A project-level goal or plan file (loaded at
session start, or named in the handoff) is CONTEXT, not a queue: a step another session owns is
not yours, even when it looks unassigned. Measured 2026-09-25 in the consumer repo: an auto-continue
prompt pointing at the project's goal file sent a documentation session into another seat's
bugfix lane, while its own handoff said "do not touch" about exactly that lane. If the thread is
blocked, say so — do not adopt another.

Read it, then **run the §0 probes** and **state the measured state**, not what the file says —
the file is the *last* truth, the command is the *current* one. If they disagree, that itself is
a finding. Remember the ID: if you later write a handoff again, update **this** one.

If the session has the agent-comm `focus` tool, update it (Phase 4b): `handoff <ID> loaded —
continuing <slug>` — so the fleet view shows the thread was picked up, not that it is still
waiting.

## `/handoff list` — what is written

```bash
ls -lt .set/handoff/*.md 2>/dev/null || echo "No handoff written."
```

Per line: ID, slug, age. Flag anything older than 30 days — but **do not delete it**: a silent
deletion is indistinguishable from there never having been a handoff. Delete on the user's
request, with `rm`.

---

## The four rules the skeleton is shaped by

1. **Every thread goes across, not just the running one.** The measured failure, in the user's
   words: *"I define several tasks in one session, and at the end it gets lost, it drops out…
   or I move to another session, but there I only deal with one of them."*
2. **Decision ≠ work.** What only the user can decide, the successor **will not** decide; if it
   is not marked, it either waits (deadlock) or gets decided for them (worse).
3. **Numbers only from commands.** See Phase 1.
4. **What cannot be rebuilt is rescued, not described.** Everything else in a handoff is a
   pointer — a path, an id, a URL — and a pointer is enough, because the thing it points at
   still exists. Scratch is the exception: it is the one carrier that dies at the same moment
   the handoff is written. See the rescue rule in Phase 1b.

## Related

- `.claude/handoff.profile.md` — this project's probes and specifics (project-owned)
- The project's own memory / knowledge base, if it has one. A handoff does **not** replace it:
  memory is what is true in *every* session; a handoff is what is open in *this thread*.
  ⚠ But it is not independent of it either — **Phase 1b**: memory reaches the successor before the
  handoff does, so anything this session wrote there is checked, and corrected if a later
  measurement disproved it.
