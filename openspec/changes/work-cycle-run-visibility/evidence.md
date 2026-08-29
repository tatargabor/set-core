# Evidence — one real change, driven end to end THROUGH THE SCREEN

Task 7.4. Recorded because the task asks for **what a run produced**, not for an exit code.

## Where it ran, and why not here

A unit driving this change would edit **this change's own `tasks.md`**, in the tree this work
is written in, and a second session was working in that tree at the same time. So the run
happened in a separate worktree — `set-core-wt-liveproof`, branch `liveproof/run-visibility`,
cut from `717df2c3` — against a disposable change, `work-cycle-live-proof`: three groups with
**declared dependencies**, one task whose wording is deliberately **not the agent's to choose**,
and a declared gate that is a real command (`python3 -m unittest`, because a fresh worktree has
no virtualenv and a gate that cannot run is not a gate).

Every start below was a click on the work-cycle panel's `start` button. Nothing was started
from a terminal.

## The sequence, and what each step produced

| # | start | verdict | gate | commit | what the tree showed |
|---|---|---|---|---|---|
| 1 | group 1 | `GROUP_DONE` | `passed` | **none — `git add failed`** | `NOTE.md` created, one line. **B-108.** |
| 2 | group 2 | `GROUP_DONE` | `passed` | `3498603b` | `proof/slugify.py`, `tests_proof/`, second line; group 1's work carried in with it |
| 3 | group 3 | `NEEDS_INPUT` | — | none | question recorded — but marked on the **blank line above** the task. **B-111.** |
| 4 | group 3 | `NEEDS_INPUT` | — | none | after the fix: `- [?] 3.1` on its own line, `status`: *awaiting an answer (1 task(s))*, nothing runnable |
| 5 | `answer --task 3.1` | — | — | — | applied; the task released back to `- [ ]`, the group runnable again |
| 6 | group 3 | `GROUP_DONE` | `passed` | `cbd8f4ab` | third line = **the maintainer's wording, verbatim**, em dash included |

Final product, `cat -A docs/work-cycle-proof/NOTE.md`:

```
group one ran$
group two ran$
group three ran M-bM-^@M-^T and a person chose these words$
```

Three groups complete, tree clean, `status` reports `1: complete · 2: complete · 3: complete`.

## What the run found that the tests could not

Both defects below were live-only. Every unit test in this change passed through both.

**B-108 — a unit does everything right and then does not commit.** Verdict green, gate green,
product on disk, `commit: {committed: false, reason: "git add failed"}`. Cause: an
`:(exclude)` pathspec pointing *inside* a gitignored directory makes git treat that directory
as explicitly named, so a silent skip becomes a hard error. The engine's own run-state
exclusion was therefore what broke the commit — in exactly the project shape this engine's
adoption note recommends. **The failing condition is created by the thing under test, on its
first run**, which is why no test could reach it. Fixed in `368ece07`, proved by step 2.

**B-111 — a question addressed to a person is attached to nothing.** The unit set itself
aside correctly and wrote the question onto the **blank line above** the task; the task kept
`- [ ]`, so `status` answered *"no answers were pending"* and offered the group as runnable.
One character: `^(?P<indent>\s*)` under `re.M` lets `\s` eat the newline, so the match starts
on the blank line that every caller then rewrites. It fires on the **first task of every
group** and nowhere else — which is where a decision reserved for a person tends to sit. Every
existing test asked about `3.2`; the fixture had contained a `3.1` all along. Fixed in
`92313420`, proved by step 4.

## What this run did NOT establish

- **6.10–6.12 / AC-37–39 stay open.** A run row on the screen carries no control that opens
  the unit's terminal, so a running unit could not be opened, a view could not be closed, and
  a finished run's recording could not be shown. The screen half is unbuilt; the API half
  ships.
- **AC-28 stays open** — the engine's own refusal still does not reach the caller (B-107).
- **AC-31 (a stale claim) was not exercised**: no run's process died mid-way. A scenario
  nobody triggered is not a scenario anybody proved.

## Two observations worth keeping

- **A re-run of a group overwrites that group's record and stream.** The unit id is
  `<change>--<group>`, not a counter, so step 3's `NEEDS_INPUT` record no longer exists —
  step 4 replaced it. Anything that wants a group's history must copy it out.
- **The panel does not poll.** After a run finished, the screen kept showing `unconfirmed`
  until its re-read button was pressed; and the re-read itself takes ~5 s for 60 changes with
  no sign that it is loading, so stale values look current in the meantime.
