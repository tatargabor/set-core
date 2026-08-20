# Bug register — defects that are not a task in any open change

Every defect **anybody reports — the user, a session, a peer agent — that does not
belong in an open change as a task** is written down here, at the moment it is
reported. Rule stated by the user on 2026-08-19, and the reason is the one that
matters: a session runs out, and a defect that lived only in the conversation
goes with it.

## The line this draws

| where it goes | what it is |
|---|---|
| `tasks.md` of an open change | in scope for that change — it is a task, not a register entry |
| **here** | anything else: found while doing something else, outside the change, or with no change yet |
| a direct commit | a measured defect fix that changes no contract — fix it, then close the entry here |

An entry leaving here becomes either a task in a change or a commit. It does not
become a memory: memory is what is true in every session, and a defect is not.

## Why this exists, measured the day it was written

Three losses on 2026-08-19 alone, all of the same shape:

- A finding from a screen review — *"the agent grid uses the top third and leaves
  the rest black … roughly 60 % of a 1900×1100 viewport is empty"* — was handed to
  another agent, never done, never marked as not done, and resurfaced only because
  that agent volunteered it at handover. The user had also asked for it twice, in
  their own words, and both askings had gone the same way.
- A missing control was reported over the agent channel by a session that then
  closed. Nothing but a chat message held it.
- A comment in `fleetCardStyle.ts` promised a minimum height the code did not
  have. Nobody was wrong on purpose; the claim simply outlived its truth.

## The two conditions that decide whether this rots

1. **Every entry names how it was MEASURED and how you would know it is fixed.**
   Without both, the register becomes a pile nobody can act on, which is the same
   as not having it. "It looks wrong" is a report; a command and its output is an
   entry.
2. **Entries are CLOSED with evidence, never deleted.** A removed entry and one
   that was never written look identical from the outside. Closing means a commit
   sha (or a change name) on the line, and the entry stays.
3. **The number is allocated by MEASURING the file, never by memory.** Measured
   2026-08-19: one session issued `B-9` and `B-10` twice, four commits apart
   (`bf33e28e`, then `a2006254`), so one handle named two different defects and
   *"B-9 is closed"* stopped being an answerable statement. Before writing an
   entry: `grep -oE '^### B-[0-9]+' openspec/bugs/README.md | sort -t- -k2 -n | tail -1`.
   The second pair was renumbered to **B-14** and **B-15**; the first pair keeps
   its numbers because an open change already cites `B-10`
   (`openspec/changes/agent-goal-and-lifecycle/tasks.md:138`).

Also binding here: [External Project Confidentiality](../../CLAUDE.md). A defect
found while looking at a consumer's data is described by its shape, never by the
consumer's name, path, or content.

## Entry format

```markdown
### B-<n> — <one line, the defect, not the symptom>
- **state:** open | closed (`<sha>`) | not-a-defect (why)
- **reported:** <date> by <user | this session | peer agent>, <how>
- **measured:** the command and its output, or a `file:line`
- **fixed when:** the check that would go from red to green
```

---

## Open

### B-1 — an agent can only be stopped through an open terminal, and closing that terminal is a detach
- **state:** open
- **reported:** 2026-08-19 by the user (*"hogyan tudlak bezárni? nincs is ilyen
  gomb?"*), relayed by a peer session
- **measured:** the route exists (`lib/set_orch/api/fleet.py:586`) and the web UI
  calls it from exactly one place — `web/src/components/FleetTerminal.tsx:200`,
  the terminal header. So stopping is reachable only for an agent that has a
  terminal AND has it open. There is no stop on the tile.
  ⚠ The peer reported this as "the screen cannot stop an agent at all"; that is
  wider than what the code says, and the narrower statement is the one to work
  from.
- **the part that is worse than a missing button:** closing the terminal panel is
  a *detach*, stated in that component's own comment against requirement 5.4 —
  the owner keeps the pty. A reader who closes it can reasonably believe they
  stopped the agent. That is a false absence in a control: the screen suggests it
  is over while the process runs.
- **fixed when:** a stop is reachable from the tile without opening a terminal,
  one agent at a time, and the confirmation names what it stops — the label and
  the pid are different things and the reader sees the label.

### B-2 — nothing typechecks `web/tests/e2e/**`
- **state:** open
- **reported:** 2026-08-19 by this session, while checking a new spec
- **measured:** the root `web/tsconfig.json` is `{"files": [], "references": [...]}`,
  so `npx tsc --noEmit -p .` checks **zero files** and exits 0 on anything.
  `npx tsc -b` builds the referenced projects, and their includes are
  `tsconfig.app.json` → `["src"]` and `tsconfig.node.json` → `["vite.config.ts"]`.
  `npx tsc -b --listFiles | grep -c tests/e2e` → **0**.
- **why it survived:** Playwright transpiles without typechecking, so a type error
  in a spec shows up as a runtime failure or not at all. And `tsc --noEmit -p .`
  *looks* like a check — it is the command a reader reaches for, and it is the one
  that measures nothing.
- **fixed when:** a tsconfig covers `tests/`, and a deliberate type error in a spec
  makes the check fail.

### B-3 — the first row of the modules panel refuses: `core-rules` is a capability with no installable module
- **state:** open
- **reported:** 2026-08-19 by a peer session and independently measured here
- **measured:** the capability report for a project lists `core-rules`, `starter`,
  `capacitor-nextjs`, `nextjs`; `POST /api/fleet/projects/<name>/install` with
  `{"module":"core-rules","dry_run":true}` → **409** `no module named 'core-rules'
  ships with this framework (looked under .../modules)`. The other three → 200.
  So the capability namespace and the installable-module namespace overlap in 3 of 4.
- **why it matters more than a 409:** it is the first row in the panel, so it is
  the first thing a reader clicks. The surface renders it correctly as a refusal —
  the defect is upstream, in the two namespaces disagreeing.
- **fixed when:** every capability the report names either resolves to a module or
  is not offered as installable, and the panel's first row is not a dead end.
- **traced 2026-08-19, and it needs a DECISION rather than a patch.** The two
  namespaces are built from two different sources and neither is wrong:
  `framework_capabilities()` (`lib/set_orch/fleet/capabilities.py:186`) derives
  `core-rules` from the directory that ships the rules, `templates/core/rules/*.md`;
  `resolve_module()` (`lib/set_orch/module_install.py:447`) resolves a name by
  globbing `modules/*/*/templates/<name>/manifest.yaml`, and the core rules have
  no manifest and do not live under `modules/`. So the report is right that the
  capability exists and the installer is right that no module carries it.
- **two ways out, and the difference is who owns the files:**
  - **(a) make it installable** — widen the resolver to build a declaration from
    the same directory the report reads. Truthful, because those rules ARE
    deployed; `set-project init` does it. ⚠ But `templates/core/rules/*.md`
    deploy **un-prefixed into the project's own namespace** and are `once: true`
    seeded (see `ae9706bb`), so this panel would gain a button that writes files
    a consumer owns. That is a write path into a foreign tree, and this repo's
    whole 2026-07-19 safety track is about not adding one by accident.
  - **(b) make the report honest** — the capability declares that this panel
    cannot install it and names what does (`set-project init`). Not a false
    absence: the claim is *this surface cannot install it*, not *these rules do
    not exist*. Cheap, and it ends the dead end.
- **recommendation: (b), and (a) only on the user's say-so.** (b) removes the
  reported defect — the first row stops refusing — without this screen growing a
  new way to write into somebody else's repository. Left undone deliberately
  rather than half-built.

### B-4 — `check_requirements` cannot fire: no shipped module declares `requires:`
- **state:** open
- **reported:** 2026-08-19 by this session, while writing the 9.17 e2e
- **measured:** `grep -ln requires modules/*/*/templates/*/manifest.yaml` → no
  matches, across all three shipped manifests (`starter`, `capacitor-nextjs`,
  `nextjs`). The check itself is wired (`lib/set_orch/module_install.py:380`) and
  raises `InstallRefused`.
- **consequence:** the "refused for a missing requirement" path is code nothing can
  trigger, and its e2e assertion has to fulfil the answer rather than provoke it.
- **fixed when:** at least one shipped module declares a real requirement, so the
  refusal can be reached by clicking — `capacitor-nextjs` requiring `nextjs` is the
  obvious candidate and should be checked against what that module actually needs.

### B-5 — an agent becomes un-instructable because a *different* tile was enlarged
- **state:** closed (`0b211f2f`) — it was the remainder of task 7.3
- **fixed:** the row is a `div` with the same guarded click the card uses, and it
  carries `FleetInstruct` in a `compact` frame. Two regression tests, both
  mutation-proven: dropping the input fails one, dropping the guard fails the
  other — and the guard is the load-bearing half, because without it every click
  inside the input would also enlarge the row.
- **reported:** 2026-08-19 by a peer session at handover, verified here
- **measured:** with one tile enlarged the others render through `AgentRow`, and
  `AgentRow` carries neither the input nor the excerpt —
  `grep -c 'FleetInstruct|Excerpt'` over its body → **0**.
- **fixed when:** a row keeps its input, so enlarging one tile does not remove the
  ability to instruct the rest.

### B-6 — 14 changes fail `openspec validate --strict`
- **state:** open, long-standing, not this thread's
- **reported:** carried forward from the handoff profile (12 on 2026-08-17)
- **measured:** 2026-08-19 15:40 —
  `for c in $(ls openspec/changes/ | grep -v archive); do openspec validate "$c" --strict >/dev/null 2>&1 || echo "$c"; done | wc -l` → **14**
- **fixed when:** the count is 0, or each remaining one is named here with a reason.

### B-9 — the shipped statusline's `Agents: N` is always 0: it reads a key the runtime does not send
- **state:** closed (`e2eb3dab`)
- **reported:** 2026-08-19 by this session, while measuring the context-window carrier
- **measured:** a project-local `statusLine` command dumping its stdin was run twice
  under a pty — once with no subagent, once in a run that spawned one
  (`Agent(Calculate 2+2)`, observed finishing on screen). The payload's top-level
  keys in BOTH captures:
  `session_id, transcript_path, cwd, prompt_id, session_name, model, workspace,
  version, output_style, cost, context_window, exceeds_200k_tokens, fast_mode,
  thinking, rate_limits` — **`agents` is not among them.** The shipped scripts read
  `jq -r '.agents // [] | length'` (`mcp-server/statusline.sh:25`, `install.sh:831`),
  so the `// []` fallback turns a missing key into an empty list and the count is
  structurally 0.
- **the class, not the typo:** a zero produced by a *missing key* rather than by an
  empty set — the shape error this repository already names. It reports "no agents"
  for a session that has them, and it does so in the one line a reader glances at.
- ⚠ **limit of the measurement, stated so it is not over-trusted:** the dump file
  holds the LAST render, which in the subagent run may have been taken after the
  child finished. So `agents` is measured absent in 2 of 2 captures, but NOT proven
  absent *while* a subagent is mid-flight. Re-check by capturing every render, not
  the last one, before concluding the key never exists.
- **fixed when:** the field the statusline counts is one the runtime actually sends
  (or the count is removed), and a session with a live subagent shows a non-zero
  figure — proven by a capture taken while the child is running, not after it.

### B-10 — `context-window-metrics` divides by a hardcoded 200 000, which is wrong for this repo's own sessions
- **state:** closed (`e52ccdc4`) — **owned by the change `agent-goal-and-lifecycle`**, listed here
  because it was found while measuring something else and predates that change
- **reported:** 2026-08-19 by this session
- **measured:** `openspec/specs/context-window-metrics/spec.md:47` requires
  `CONTEXT_WINDOW_SIZE = 200_000` as the divisor of every utilization percentage.
  The runtime reports `context_window.context_window_size` **per model** in the
  statusline payload. Re-measured 2026-08-19 on an agent started with the
  framework's own default argv (`claude --dangerously-skip-permissions`,
  `ownerd.py:65`, model `claude-opus-5`): its status line read
  **`Ctx: 4% (36801/1000k)`** — a 1M window. The constant renders that same
  session as **18 %**.
- **fail direction:** it over-reports utilization by the ratio of the real window to
  200 000 — measured at **5×** on the framework's own default agent, so a session
  with 96 % of its context free is displayed as nearly full. That is the direction
  that triggers unnecessary action.
- **fixed when:** the divisor comes from the reported size, an unreported size
  renders as unknown rather than as a percentage, and a session on a non-200k model
  shows a figure that matches what the runtime says.

### B-8 — the log view does not open at the latest, and its tool lines say nothing
- **state:** closed (`e52ccdc4`)
- **reported:** 2026-08-19 by the user — *"scrollbar mindig alul kell legyen hogy
  latest mutassa, illetve a Bash és tool feliratok nem mutatnak semmit a lognál
  csak a helyet viszok, át kell gondolni"*
- **measured:** the conversation list renders `16:24 Bash ↵1` rows between the
  spoken turns; the row carries a tool NAME and a count and nothing about what
  the tool did, so a reader learns only that something happened. And the scroll
  box starts at the top, so the newest turn — the one the reader came for — is
  off screen on any log with history.
- **fixed when:** the box is scrolled to the newest turn on open and stays there
  while new turns arrive unless the reader has scrolled away; and a tool line
  either carries something a reader can act on or does not take a row.

### B-14 — the project rows are thin, and a richer design that once existed is gone
- **state:** closed (`28ef5ce7`)
- **reported:** 2026-08-19 by the user — *"még mindig kicsik a projekt csempék.
  korábban vagy 3 soros status állapotokkal meg minden volt tervezve és egyszer
  láttam is, az hova lett? ki kell bővíteni minden funkcióval amit érdemes látni
  ikonokkal"*
- **searched first, and the answer was NO:** the earlier three-line design is in
  neither `design.md` nor the file's git history (six commits, all recent). What
  IS written down is the spec's own word — it says *project TILE* while the
  implementation was a thin row. That gap is what got rebuilt, rather than a
  design invented on top of a half-remembered one.
- **fixed when:** the project row carries what is worth seeing, in icons, and the
  earlier design is either restored or explicitly superseded with a reason.
- **closed:** `28ef5ce7` — three lines: name · states + agent count + conflict ·
  capability marks + oldest stillness + sources. The earlier design is explicitly
  SUPERSEDED, not restored: the search above found it nowhere, so the spec's own
  word (*project tile*) is what got built.

### B-15 — an agent tile can be almost entirely empty while the log has plenty to say
- **state:** closed (`f64c7554`)
- **reported:** 2026-08-19 by the user — *"nem hiszem hogy üres kellene legyen
  akár egy agent is., már biztosan van róla valami log, info"*
- **measured:** a tile whose excerpt is one short sentence leaves the rest of its
  ~500 px empty, while the same agent's log endpoint has turns and tool activity
  to show.
- **fixed when:** a tile with room to spare fills it from what is actually known
  about the agent, rather than leaving the space blank.
- **closed:** `f64c7554` — a tile shows its LOG by default
  (`web/src/pages/Fleet.tsx:458-460`), and clicking it hands over the live
  terminal. Measured live at 2026-08-19 17:0x: 3 tiles showing a log, 2 of them
  clickable — exactly the 2 the framework started.

### B-11 — the excerpt spills over several lines where one and an ellipsis would do
- **state:** closed (`e52ccdc4`)
- **reported:** 2026-08-19 by the user — *"ez a több soros first message az agent
  után értelmetlen. le kell vágni egy sorba aztán ..."*
- **measured:** the tile clamps the excerpt at 12 lines since `c4f4842f`, which
  was an overcorrection: it filled the taller tile with ONE long message instead
  of with information.
- ⚠ **reported together with B-10 and they pull in opposite directions on the
  same space** — one line for the message, and the freed space filled with
  something structured rather than more prose. Fixing either alone gets it wrong.
- **fixed when:** the excerpt is a single line ending in an ellipsis, and what
  fills the tile is not the excerpt.

### B-12 — inside a grid tile the terminal and the log stop at a fixed height and leave the column empty
- **state:** closed (`e52ccdc4`)
- **reported:** 2026-08-19 by the user, twice — *"oszlop engedné de nem megy le
  alulra a terminál … kihasználni az adott hasábot, területet amit a layout tesz"*
  and *"sima log nézetben jobb oldalt látjuk hogy félbevágja, nem húzza le a log
  nézetet a terület aljáig"*
- **measured:** the tiles themselves DO fill their row since `c4f4842f`; what
  does not fill is what is inside them. `FleetTerminal`'s host is `h-72` and
  `LogPanel`'s scroll box is `max-h-80` unless the tile is enlarged or full
  screen — so in a grid tile both are cut at a fixed height with the rest of the
  column blank below.
- **why the first fix missed it:** `c4f4842f` replaced the guessed `62vh`/`55vh`
  with flex **only on the full-screen path**, because that was the path in the
  report. The same guess in the ordinary path was left standing, and it is the
  one a reader meets every time.
- **fixed when:** in any tile that has height to give, the terminal and the log
  take what is left, with a floor so a short tile stays usable.

### B-13 — a terminal in a narrow column re-wraps into an unreadable strip
- **state:** closed (`e52ccdc4`)
- **reported:** 2026-08-19 by the user — *"kevés a hely de hülyén tördel a
  terminál … nagyban jól működik"*
- **measured:** `FitAddon.fit()` sets the column count from the container's
  width, and the resize is sent on to the pty. In a narrow tile that means the
  AGENT re-renders its own terminal UI at ~30 columns, which no terminal program
  is designed for — the screenshot shows a body wrapped to a third of the width
  with a one-character column stranded at the right edge.
- **the shape, and why "wrap better" is the wrong fix:** a terminal is a
  fixed-grid device. Its content was laid out by the program for a given number
  of columns, so re-flowing it is not a rendering choice — it destroys the
  layout the program produced. The repair is a FLOOR on the columns plus a
  window onto the result, never a cleverer wrap.
- **fixed when:** a narrow tile shows a scrollable window onto a terminal that is
  still at least 80 columns wide, and the pty is never told it is narrower.

### B-16 — a terminal re-attached after a project switch draws a broken screen until a keystroke repairs it

- **state:** open — the cause is found and the fix is shipped in code, and the
  entry stays open because nobody has yet performed the reported recipe against
  the running build. A fix is a fix when somebody LOOKS; until then this is a
  repair of the mechanism the screenshot is consistent with.
- **reported:** 2026-08-19 by the user — *"terminal also status bar elromlik ha
  projektet valtok, beleirok, majd visszavaltok"*, and then the half that names
  the cause: *"beiras utan megjavul"*
- **measured:** reported with a screenshot, NOT yet reproduced by a session —
  said plainly so nobody quotes this as a measurement. The recipe is exact:
  switch to another project, type into an agent there, switch back. The agent's
  status bar comes back mangled — in the screenshot only `34236` and
  `· ← 7 agents` survive of a line that is normally full width — and any
  keystroke restores it.
- **what the repair-on-keystroke rules OUT, which is the useful half:** the
  socket is fine, the pty is fine and the buffer is fine. A keystroke changes
  nothing about any of them; what it does is make the REMOTE program repaint.
  So the screen is stale, not lost — a redraw that never happened rather than
  bytes that never arrived.
- **where to look first:** switching projects unmounts the tile, so coming back
  is a fresh attach: `FleetTerminal` replays the buffered screen and a
  `ResizeObserver` refits xterm. A replay written at one column count and
  refitted to another leaves exactly this — a line that was drawn for a
  different width, with nothing prompting the far end to redraw it. The column
  FLOOR (80) shipped in `387ba8c2`, so the tile's width and the pty's width are
  deliberately allowed to differ, which is what makes the ordering matter.
- **fixed when:** switch away, type, switch back — the status bar is whole
  before anything is typed. Prove it the way this repo proves a fix: break the
  ordering again and watch the check go red.
- **what was found, and it is structural rather than a guess:** the `attached`
  ack reaches the browser BEFORE any replay byte — `lib/set_orch/api/fleet.py`
  sends it, then starts the output pump — and it carried how MUCH was replayed
  and never what SHAPE it was. So the viewer fitted to its own tile and then
  rendered a screen that a program had laid out for some other width. A terminal
  is a fixed-grid device: that does not adapt the screen, it destroys it, and
  silently, because the result still looks like a terminal.
- **the repair, in two ordered steps:** the ack now carries the pty's geometry,
  READ from the master fd with `TIOCGWINSZ` rather than remembered (a stored
  copy drifts the moment anything else resizes the window); the viewer adopts
  that shape before the first replayed byte, and sends its own size back only
  once the replay has landed — counted down from `replayed_bytes`, with a
  one-second fallback so a short replay cannot leave the pty stuck.
- **proven by mutation, not by a green run:** 4 of 6 client tests fail on the
  old ordering, the 5th on substituting a default geometry for `null`, and 2 of
  4 owner tests fail when the size is remembered instead of read. Restores
  verified by file identity.

### B-17 — set-core's PUBLISHED history still names private consumer projects, and a fork network makes that permanent
- **state:** open — deliberately, and the decision is the entry
- **reported:** 2026-08-19 by the user — *"ellenőrizd, hogy ... ne tudjon kimenni
  personális adat token projektspecifikus olyan, ami problémát jelent"*
- **measured:** `git grep -lE '<slugs>' origin/main` → **34 files**;
  `git log origin/main --format='%s%n%b' | grep -icE '<slugs>'` → **8 commit
  messages**; the published tag `refs/tags/orch/complete` carries **10**. The slug
  list is built at run time from `~/.config/set-core/projects.json`, never stored
  in the repo.
- **why it is not being fixed the obvious way:** `gh repo view` reports **6 forks
  and 30 stars**. GitHub keeps a fork network's objects reachable by SHA, so a
  `filter-repo` + force-push would rewrite every SHA, break every clone, and still
  not remove the content. The five sibling public repos have **0 forks**, and all
  five were fully scrubbed instead (`set-agent-comm`, `set-copilot`, `set-atlas`,
  `set-demo`, `set-claude-handoff`).
- **what was done instead:** the working tree is clean (`set-leakscan --tree` →
  0 findings), and both gates are installed so nothing new joins it.
- **how you would know it changed:** `set-leakscan --tree` in this repo reports
  only `consumer-name:commit-message` entries, all of them reachable from
  `origin/main` — never a content finding, and never one in `origin/main..HEAD`.

### B-18 — two local backup tags hold the pre-scrub content, and `push --tags` would republish it
- **state:** open
- **measured:** `git tag -l 'backup-*'` → `backup-pre-scrub-2026-07-24`,
  `backup-preslugscrub-20260731`; each resolves to a commit whose history carries
  8 leaking commit messages. `git ls-remote --tags origin | grep backup` → **empty**,
  so they are local only *today*.
- **why it matters:** this is rule 8 of `.claude/rules/release-safety.md` observed
  in the wild — a scrub's own leftovers. A single `git push --tags`, `--mirror` or
  `--all` publishes exactly what an earlier scrub removed.
- **how you would know it is fixed:** either the tags are deleted, or a push
  refspec policy exists that cannot name them. Verified by
  `git ls-remote --tags origin | grep -c backup` staying 0 after any push.

### B-19 — the public GitLab mirror of set-core was not updated with the cleanup
- **state:** CLOSED 2026-08-20. `git push gitlab main` → `83245a86..d193b775`;
  `git ls-remote <gitlab> main` and `git rev-parse HEAD` now return the same
  `d193b775`. Verified by comparing the two, not by the push reporting success.
- **measured:** `curl .../api/v4/projects?per_page=100` anonymously lists exactly
  two public projects on the self-hosted instance: `root/set-core` and
  `root/craftbrew-run`. The mirror's newest commit is **2026-07-09**, i.e. it
  predates the cleanup entirely. (`root/craftbrew-run` holds only GitLab's default
  README — nothing to clean.)
- **how you would know it is fixed:** the mirror's tip equals the GitHub tip, and
  `set-leakscan --tree` run against a fresh clone of it is clean.

### B-20 — set-voice-agent-delivery's two remotes have diverged: GitLab refused the scrubbed history
- **state:** open
- **measured:** `git push --force gitlab main` →
  `GitLab: You are not allowed to force push code to a protected branch on this
  project` / `[remote rejected] ... (pre-receive hook declined)`. GitHub took the
  same push. That GitLab project is **not** in the public list, so nothing is
  exposed — but the two copies now hold different histories, and the GitLab one
  still contains a real phone number.
- **how you would know it is fixed:** unprotect `main` on that project, force-push,
  re-protect; then `git rev-parse origin/main gitlab/main` returns one SHA twice.

### B-21 — a project the screen SHOWS, with a start control next to it, refuses the start

- **state:** closed (`ec391a78`)
- **reported:** 2026-08-19 by the user, with a screenshot: the panel header names
  the project and its path, offers *start an agent*, and the answer is
  *"… is not a project this screen knows; register it first"*
- **measured, in-process against the running server:** the list serves **49**
  projects; `_known_roots()` — the guard the start endpoint asks — knew **39**.
  **10 projects were shown with a start control and refused**: 9 supplied only by
  the messaging registry, 1 by a live process whose root the guard's own
  enumeration missed.
- **cause, and it is not about any one project:** the guard ENUMERATED ITS OWN
  SOURCES — the registry, plus the roots of discovered agents — which is a second
  definition of *what this screen knows*. It was correct while the list had those
  same two sources and went wrong silently when a third arrived. The union's
  downstream filter had already been bitten by the same third source
  (`api/fleet.py`, the note at the `if not members and not project.sources`
  line); that one was fixed and this one was not.
- **the class:** *completing a set means auditing everything downstream of it* —
  any later step that re-states the set is a copy, and it drifted the moment the
  set changed. The guard now asks the list rather than rebuilding it, so a
  fourth source cannot reintroduce this.
- **a second finding fell out, and it nearly caused a mirrored bug:** the fix's
  first docstring claimed archived projects stay out, taken from
  `discover_projects`'s own docstring — *"an `archived` project is excluded by
  every other surface in this framework, so it is excluded here too"*. Measured:
  **19 of the 49 served projects are archived**, and the screen shows them all.
  Believing that sentence and filtering here would have rebuilt the same
  divergence in the other direction. See B-22.
- **proven by mutation, both directions:** restoring the two-source guard fails
  2 of 4 tests; making the guard accept everything fails 2 of 4 — a different 2,
  including the one that keeps the protection. Restore verified by file identity.
- **⚠ one thing this fix does NOT answer.** The refusal told the reader to
  *register it first*, and the screen offers no way to do that. `set-project
  init` does register (`bin/set-project`, the *Add project to registry* branch),
  but the reported project is not in `~/.config/set-core/projects.json` — so
  either that command did not run for it or it ran under another name. Not
  investigated further, and not guessed at here.

### B-22 — `discover_projects`'s docstring claims an archived filter the code does not have

- **state:** open
- **reported:** 2026-08-19 by this session, while fixing B-17
- **measured:** the docstring says *"an `archived` project is excluded by every
  other surface in this framework, so it is excluded here too — but the flag is
  carried rather than dropped"*. The code below it sets `archived=` on the entry
  and never filters on it; `grep -n archived lib/set_orch/api/fleet.py` finds one
  use, and it is the field being copied into the response. Live: **19 of 49
  served projects are archived**, all shown.
- **why it is worth an entry rather than a one-word edit:** this is the *comment
  claiming a guard the code does not have* class, and it already cost something —
  it was read as fact while writing B-17's fix and nearly produced a mirrored
  version of the very bug being repaired. A comment that is wrong is worse than
  none, because the next reader stops looking.
- **it needs a DECISION, not just a rewrite:** either the sentence is stale and
  should describe what the function does, or the filter was intended and is
  missing — in which case 19 projects are on screen that this framework's other
  surfaces exclude, which is a bigger question than a docstring.
- **fixed when:** the docstring and the code agree, and whichever way it is
  settled, a test holds it — the wrong reading is what has to be unable to come
  back.

### B-23 — a refused send says it failed four times and offers a remedy for a cause it never reached

- **state:** closed (`1d8f41a4`)
- **reported:** 2026-08-19 by the user with a screenshot — *"send comand hibára
  futott"*
- **measured, off the reported card, in render order:** `refused` ·
  *the agent does not have it* · *the send was not made*, then *the send did not
  happen*, then the channel's own reason, then — in **amber** — a remedy about
  missing waiters. Four statements that it failed, one cause, and the amber went
  to the wrong one.
- **the defect is not the wording, it is a claim about a stage never reached.**
  `offerWaiterRemedy()` fired on `waiters_here === 0` alone. That count is a
  true measurement of a condition the send never got to: the channel refused it
  at the room check, so nothing left, and the sentence it produced —
  *"every instruction sent here sits unread"* — is present tense about messages
  that do not exist. Same class as a count taken from a declaration instead of
  from the data: the number is right and the thing it is offered as evidence FOR
  was not in play.
- **and the colours were inverted.** Amber means *needs attention* everywhere on
  this screen. The remedy that could not work had it; the remedy that would have
  worked — the channel's own *join the room first, then send* — was `fg-ghost`,
  the faintest thing on the card. A colour spent on the wrong thing is worse
  than no colour, because it is followed.
- **fixed:** the remedy requires that a send was actually made (`accepted !==
  false`; an ABSENT `accepted` is still offered, so an older server does not
  lose a real remedy); after a refusal *the agent does not have it* is dropped
  as a restatement of the first fact and the delivery state stays in the DOM
  marker; the channel's notices are no longer the quietest line.
- **proven by mutation:** restoring the unconditional remedy fails 2 tests,
  restoring the restatement fails 2 (one of them a pre-existing 409 test),
  returning the notices to `fg-ghost` fails 1. Restores verified by file
  identity. 570 web unit tests green, build exit 0.
- **⚠ what is NOT fixed, deliberately:** the label/note pair still reads
  *refused* / *the send did not happen*, which is one restatement remaining. It
  is left because the note table is static and the fix that reads well —
  suppressing a generic note when the channel gave a specific one — would also
  drop `held`'s note, which carries something no reason does (the hold expires
  on its own). Worth a decision, not a quiet edit.

### B-24 — `CLAUDE.md` sends every session to `START.md`, and that file does not exist
- **state:** open
- **measured:** `CLAUDE.md:807` reads *"See [START.md](START.md) for application
  startup commands (install, dev server, database, tests)."*; `ls START.md` →
  no such file, and `git log --diff-filter=D -- START.md` finds no deletion
  either, so it was never committed.
- **why it matters more than a broken link:** it is in the *rule book*, which is
  loaded into every session's context. An agent asked how to start the app is
  pointed at nothing, and the failure is silent — a missing file reads as
  "nothing to see" rather than as an error.
- **⚠ WIDER THAN ONE REPOSITORY, measured 2026-08-20.** `set-project init`
  *writes this sentence into every consumer's `CLAUDE.md`* ("Added Getting
  Started reference to CLAUDE.md"), and deploys no `START.md` beside it —
  `find templates modules -name START.md` → 0. Across the registry: **35
  projects carry the reference and 20 of them have no such file.** So this is
  not set-core's own oversight; it is a defect the deploy path propagates, and
  it grows by one with every init. Found while running a first init into a
  project that had never had one.
- **how you would know it is fixed:** either `START.md` exists and lists the
  install / dev-server / database / test commands, or the sentence names a file
  that does.

### B-25 — three repositories tracked a file their own `.gitignore` claimed to exclude
- **state:** closed for the three found (one public `set-*` project and two
  private ones); open as a *class* until the deploy path carries the check
- **measured:** `git check-ignore --no-index -q <path>` over `git ls-files`.
  **The `--no-index` is the whole finding**: without it git refuses to call a
  TRACKED path ignored, so the obvious form of this check returns zero for
  exactly the condition it exists to detect. An earlier report in this session
  stated "0 in all 16 repositories" on the strength of that broken check.
- **what it had been shipping:** a real phone number (`contacts.yaml`, added to
  `.gitignore` by a commit literally titled *remove personal data from repo* —
  with no `git rm --cached` beside it, so the intent was recorded and the effect
  never happened); a config file; and a **dictation transcript with 16 spoken
  entries**.
- **how you would know the class is closed:** `set-project init` deploys a
  `pre-push` hook running `set-leakscan`, whose `ignored-but-tracked` category is
  enforced regardless of remote visibility.

### B-26 — the dashboard's optional Discord bot fails on startup, and the traceback is the last line before a 40-second silence
- **state:** open. Not blocking: the failure is caught, and the service does come
  up — but only after a wait long enough that the first two checks after a
  restart both answered "not listening".
- **measured:** `systemctl --user restart set-web`, then
  `journalctl --user -u set-web`:
  `[SET] Discord bot startup failed: module 'discord' has no attribute 'Intents'`
  at `lib/set_orch/discord/__init__.py:65`, from `server.py:54`. A `discord`
  module IS importable — it simply is not the library this code expects, so the
  import succeeds and the attribute access is where it fails.
- **the part worth fixing, which is not the bot:** the traceback is printed at
  the exact moment the service looks dead from outside, so it reads as the cause
  of an outage it has nothing to do with. Two `curl` calls returned `000` after
  the restart while the process was still loading 40 projects; a third, a minute
  later, returned `200`. A reader following the obvious evidence would have gone
  to debug Discord.
- **how you would know it is fixed:** the startup path either does not attempt a
  bot whose library is absent, or reports the attempt as skipped rather than as a
  traceback; and the service says when it is *ready to serve*, distinctly from
  when it started. A restart followed by an immediate `curl` should then not be
  ambiguous.


### B-27 — one docking test fails about one full-suite run in ten, and passes alone

- **state:** open
- **reported:** 2026-08-20 by this session, while running the web suite for an
  unrelated verification pass
- **measured:** `npx vitest run` over the whole web suite, ten times.
  **Two runs failed, both on the same test** —
  `fleetDockingSurface.test.tsx::undocks by pressing the edge it is already on,
  so the control is never a dead end` — and eight passed 675/675. The same file
  alone: 12/12. The file together with the suite that was suspected of polluting
  it (`fleetTilePrecedence`): 21/21, in both orders. At `HEAD` with this
  session's working-tree changes stashed: 12/12.
- **what that rules out, and why it is worth writing down:** the first failure
  arrived immediately after this session added tests, so the obvious reading was
  *my change broke it*. It did not — the two runs that isolate the pair are the
  evidence, and without them the next step would have been to "fix" a test that
  was never wrong. A flake and a break look identical from one run.
- **whose it is:** the `fleet-panel-layout` thread's, not this one's. Recorded
  rather than repaired here — the file was committed by another session and is
  under active work.
- **fixed when:** the CAUSE is asserted, not the symptom. A count of green runs
  is what this register already warns against: *a symptom that stops appearing
  is not a repair*, and a reproducer is a measurement with a timestamp. The
  useful shape is the one that worked for task 10.3 — find what makes it
  order- or timing-dependent and make THAT fatal, so the check does not depend
  on how the suite happens to be scheduled.

### B-28 — the no-seat sentence is repeated on every tile instead of said once

- **state:** open
- **reported:** 2026-08-20 by this session, from a screenshot of the running
  fleet screen
- **measured:** three agent tiles on one panel, each carrying the identical grey
  line *"no input: this session has no seat on the messaging bus"* — one row per
  tile, for one fact about the machine. Most agents on this host have no seat,
  so the count scales with the fleet.
- **why it is a defect and not a preference:** this repository already made the
  same call in the same screen and wrote a test for it —
  `tests/unit/test_fleet_api.py::test_the_reason_a_terminal_is_unavailable_is_said_once_not_per_row`.
  The terminal's unavailability is stated once at the top; the seat's absence is
  stated per row. Two identical situations, two different answers, and the
  inconsistent one is the one nobody tested.
- **⚠ what a fix must NOT do:** the sentence exists because task 4.4 requires the
  producer's reason to stand WHERE THE INPUT WOULD BE — deleting it from the
  tile and saying nothing would be the false-absence direction, which is what
  the amber-to-grey change of the same line already had to correct. The shape
  that works is the terminal's: once at the top, with the tile marking that it
  is covered by that statement rather than restating it.
- **fixed when:** a panel of N seatless agents carries the sentence once, every
  tile still says it cannot be typed into, and a test asserts BOTH — the count
  is one, and no tile is silent about its own state.


### B-30 — one unanswered owner poll unmounts the open terminal, which detaches it and costs a 64 KB replay

- **state:** open
- **reported:** 2026-08-20 by the user — *"időnként megáll a fleet view,
  connectionget ir és 1 perc mulva all vissza"* — together with the question the
  entry has to answer first: does anything get reset or suspended while it says
  that. It does not; see the last bullet.
- **measured:** the chain is four hops and every one of them is a `file:line`:
  - `connecting…` is only ever the MOUNT state — `web/src/components/FleetTerminal.tsx:100`
    sets it as the initial phase and nothing sets it again; a socket that drops
    while attached renders `closed` instead (`FleetTerminal.tsx:275`). So the word
    the user reads is proof of a REMOUNT, not of a reconnect.
  - the terminal is rendered conditionally: `web/src/pages/Fleet.tsx:1481` —
    `terminalOpen && offer.kind === 'available'`; the docked list filters the same
    way (`Fleet.tsx:1865`).
  - `available` requires `population === 'started-here'`
    (`web/src/lib/fleetTerminal.ts:87`), and the API downgrades EVERY agent to
    `unknown` when the owner could not be asked — `lib/set_orch/api/fleet.py:63-77`
    (`_owned_by_pid()` returns `None` on any `OwnerClientError`) and `:108-110`.
  - that call's read timeout is 30 s (`lib/set_orch/fleet/owner_client.py:36`), so
    one slow or refused answer covers several 5 s poll cycles — which is the
    minute the report names.
  - the journal shows the consequence in pairs, e.g. `12:16:15 detached from
    consumer-a-finance` / `12:16:26 attached to set-core-fleet (65536 replayed
    bytes, truncated=True)` — every re-attach re-sends the 64 KB tail.
- **what is NOT happening, because the question was asked:** nothing is reset and
  nothing is suspended. The unmount closes the browser socket only; the server
  logs `a browser detached` and the owner keeps the pty (task 5.4,
  `lib/set_orch/api/fleet.py:1098-1101`), so the agent runs through it. The screen
  loses the view, never the session.
- **caught in the act, 2026-08-20 12:30–12:37**, and the cause is NOT the owner —
  the probe (2 s sampling of `owner_reachable` and the population split) recorded
  `owner=True` on every answered poll. What it recorded instead:
  - `12:30:38 → 12:36:16` — the endpoint stops answering entirely: four samples at
    the probe's own 60 s ceiling (`lat=60.10 TimeoutError`). The process was alive;
    it just did not answer. The machine was under memory pressure at the time
    (`free -h`: 23 Gi of swap in use, load 5.6), with a 1.5 GB `next-server` and a
    vitest run on it — an environment fact, not a framework one, but the surface
    turns it into a blank terminal.
  - `12:36:17 → 12:37:48` — `systemd`: `Stopping SET Web Dashboard…` then
    `Started`, **91 s apart**, with `connection refused` throughout. That is
    `TimeoutStopUSec=1min 30s` exactly, and it is its own defect: see B-31.
  - `12:37:48` onwards — all five terminals re-attach, 65536 replayed bytes each.
  So the minute in the report has two producers, and the tile-unmount chain above
  is what turns either of them into `connecting…` rather than into a message.
- **fixed** in `8b8f60f5` (client), and the fix is the distinction the API already
  draws surviving the trip: `resolveTerminals` now takes `null` for *nobody could
  be asked* and filters nothing on it, while `[]` still means *asked, holds
  nothing*. Two narrow helpers carry the rest — `rememberTerminalLabels` (pid →
  last CONFIRMED label, rebuilt on every answer so it cannot go stale) and
  `offerWithRemembered` (upgrades `unknown` only, and only while the pane is
  already open, so no unperformable offer is ever made).
  - **verified by LOOKING, not only by counting:** the running screen with the
    fleet answer rewritten to `owner_reachable: false` / every agent `unknown` /
    no label — the terminal **stayed and stayed `attached`**, and the amber
    header appeared. Before/after: `b30-{1-normal,2-owner-silent}.png`.
  - 730/730 web unit tests, 6 new, three mutations each caught (null-as-filter →
    2 failures; `offerWithRemembered` neutered → 2; memory rebuilt without an
    answer → 1).
- **⚠ what is NOT fixed by this, and stays open:** the first producer in the
  measurement above — the six minutes in which the endpoint answered nothing at
  all under memory pressure. The screen now says what it does not know instead of
  taking the terminal away, which is the honest failure, not the absence of one.
- **⚠ the wiring landed in a file another thread is rewriting.** `Fleet.tsx` held
  457 deletions of parallel work when this was committed, so the helpers and the
  tests are in `8b8f60f5` and the call sites are not. They are in the working
  tree and will land with that thread's commit — see B-32.


### B-31 — stopping set-web takes 91 s, so any restart is a 91 s hole in the dashboard

- **state:** open
- **reported:** 2026-08-20 by this session, from the journal while measuring B-30
- **measured:** `systemctl --user show set-web -p TimeoutStopUSec` → `1min 30s`, and
  two of today's three stops used every second of it:
  - `10:09:01 Stopping…` → `10:10:32 Stopped` → `Started` — 91 s
  - `12:36:17 Stopping…` → `12:37:48 Started` — 91 s
  - `09:29:25 Stopping… / Stopped / Started` — same second
  91 s is not a slow shutdown, it is the timeout expiring and systemd sending
  `SIGKILL`. Throughout the hole the port answers `connection refused` (probe log),
  so every open terminal drops and every poll fails.
- **cause found, and both candidates refuted first.** The journal says it in one
  line: `INFO: Waiting for background tasks to complete.` uvicorn's
  `timeout_graceful_shutdown` defaults to `None` — *wait for every running task,
  with no limit*. Refuted along the way, by measurement rather than by argument:
  - **not the WebSockets.** All three open terminals closed in the same second as
    `Stopping…` (`connection closed` ×3, `detached` ×3), and an isolated instance
    with an open terminal WebSocket exited in **0.5 s**.
  - **not `watchfiles`.** Same isolated measurement, same 0.5 s.
  - what held it were unfinished HTTP request tasks — the same six minutes in
    which the endpoint answered nothing at all (B-30's first producer).
- **fixed** in `532026d5`: `timeout_graceful_shutdown=10`
  (`SET_WEB_GRACEFUL_TIMEOUT` overrides), with three tests and two mutations.
  The instrument was proven before it was adopted: a minimal app with one stuck
  request was **still alive 60 s** after `SIGTERM` with the default, and exited in
  **10.5 s** with the timeout set.
- **the fix is RUNNING** since the 20:23 restart (the process started after the
  commit, so it loaded the patched `cli.py`), and that restart took **2 s** —
  which proves nothing about the fix, because there was no stuck task to wait
  for. The old code would have taken 2 s too. Recorded so the number is not
  mistaken for evidence later.
- **⚠ still open: the closing check has been ATTEMPTED and the instrument ate it.**
  To make a request genuinely hang, an isolated instance was given a *silent*
  owner socket (accepts, never answers) so `OwnerClient` would sit on its 30 s
  read timeout. Results: `GRACE=10` → 28.6 s, `GRACE=2` → 28.0 s, and — the line
  that settles it — **no stuck request at all → 25.5 s**. The shutdown time is
  therefore dominated by the silent socket the measurement itself installed, not
  by the graceful window. Same defect class as the watcher count measured while
  the kernel table was full: *a resource meter cannot be trusted while the
  measurement is holding the resource.*
- **what would close it:** a real `Stopping…`/`Started` pair on the live service
  taken while a request is actually hanging — i.e. the next restart that happens
  under load. Single-digit seconds closes it; anything near 90 s reopens the
  cause. Do not substitute the isolated rig: it has now been shown to answer a
  different question.
- **why it is worth its own entry:** it converts a routine `restart` — which
  agents and the user both do — into a minute of dead dashboard, and B-30's tile
  chain makes that minute read as `connecting…` rather than as "the server is
  restarting". A `SIGKILL`ed server also never runs its shutdown path.
- **fixed when:** `systemctl --user restart set-web` completes in single-digit
  seconds with terminals open, and the journal shows `Stopped` without the
  timeout — measured, not assumed, from the `Stopping…`/`Started` timestamps.


### B-32 — two agents that BOTH staged only their own paths still lose a commit to each other, because the index is shared

- **state:** open
- **reported:** 2026-08-20 by this session, after it happened to this session
  while archiving `fleet-panel-layout`.
- **measured, on the real incident:** this session staged exactly its own 8 paths
  (`git add openspec/changes/fleet-panel-layout openspec/changes/archive/… openspec/specs/fleet-dockable-views openspec/specs/fleet-panel-dividers`),
  `set-leakscan --staged` confirmed 8 files, and the following `git commit` printed
  `nothing to commit, working tree clean`. The 8 files are in **`066e6233`**, a
  third thread's *"plan(fleet-pm-mode)"* commit — 16 files, 1165 insertions — whose
  message says nothing about any of them. Verified with
  `git log --oneline -3 -- openspec/specs/fleet-dockable-views/spec.md`.
- **measured, on the mechanism, in a throwaway repo:** the existing rule does not
  defend against this. `.claude/rules/cross-cutting-checklist.md` prescribes
  `git add <path>` instead of `git add -A` — that covers only the sweep of
  *unstaged* work. Two agents each staged one file of their own, then agent A ran
  `git commit` with **no pathspec**: the commit carried both files. There is one
  index per checkout, so a pathspec-less commit publishes whatever anybody staged.
- **why this is the expensive direction:** the content survives, so nothing errors
  and no test notices. What is destroyed is the *attribution and the message* — the
  losing agent's commit message, with its evidence, never exists, and the other
  side's `git status` reads CLEAN, which is indistinguishable from "my work is gone".
- **the cure, measured in the same repo:** `git commit -- <paths>` committed only
  the named path, and the other agent's staged entry **survived in the index,
  untouched**, and was absent from the commit. One limitation measured: the form
  fails with `pathspec … did not match any file(s) known to git` for a path git does
  not yet track, so `git add <own paths>` is still required first — the pathspec
  belongs on the commit *in addition to*, not instead of, the add.
- **⚠ what a fix must NOT do:** it must not block every pathspec-less commit
  unconditionally — a gate that fires daily on nothing gets disabled, and solo work
  in a private checkout is not the hazard. And it must not try to repair an incident
  after the fact by amending or rebasing the other thread's commit: that takes back
  what another agent is holding right now, which this repository already ruled is
  more expensive than a badly grouped commit.
- **fixed when:** an agent cannot produce a commit carrying a path another session
  staged. Demonstrated by a test that stages a foreign path, runs the guard over a
  pathspec-less `git commit`, and sees it refuse with the `--` remedy named; plus
  the same guard refusing `git add -A`. And the refusal must NOT fire when every
  staged path was staged by the committing session.

### B-33 — PM mode presents an agent it cannot show and cannot address, and then the full screen is empty

- **state:** open
- **reported:** 2026-08-20 by the user, with a screenshot — *"PM Mode bekapcsolva
  es nem jon be afelulet"*.
- **measured, in the browser** (`localhost:7400`, PM mode on, 1516×784 viewport):
  the overlay renders — header, counts, footer buttons are all there — and the
  content area is **two lines of text over ~700 px of black**: *"The framework
  holds no terminal for this agent…"* and *"no input: this session has no seat on
  the messaging bus"*. `web/src/components/FleetPm.tsx:295` is the branch: when
  `agent.terminal_label` is null it renders a heading, a warning and `FleetInstruct`
  — and `FleetInstruct` returns a single grey line when there is no seat
  (`web/src/components/FleetInstruct.tsx:174`). Nothing else.
- **measured, that there IS something to show:** for the presented pid the log
  endpoint returns a full conversation —
  `curl -s localhost:7400/api/fleet/agents/<pid>/log?limit=8` → 8 turns with text,
  and the fleet payload carries `excerpt` and `excerpt_from` for the same agent.
  So the emptiness is the surface's, not the agent's.
- **measured, how ordinary this is:** `/api/fleet/agents` → **3 of 20** live agents
  have `terminal_label: null` (`population: foreign` — the framework did not start
  them), and **2 of the 4** currently queued by PM mode are among them. This is not
  an edge case; it is half the queue.
- **the same finding already exists one screen over, and was fixed there:** B-10,
  *"nem hiszem hogy üres kellene legyen akár egy agent is, már biztosan van róla
  valami log, info"* — the fix was `TileActivity` (`web/src/pages/Fleet.tsx:501`),
  which renders the log where the tile would otherwise be blank. PM mode never got
  it, and PM mode is the surface where the emptiness costs most: it is full screen,
  so there is nothing else on it.
- **⚠ a second defect, narrower, NOT fixed by the above:** the queue does not
  consider whether an item can be answered at all. Measured on the same snapshot:
  `/api/fleet/pm` presented pid 3202485 (no pty, no bus seat — nothing the reader
  can do) while the queue also held 113100 (`set-core-bugfix`) and 183020
  (`itline-web-animtoolok`), both with a terminal. A mode whose promise is
  *"whichever is waiting on you"* spent the screen on the one item that cannot be
  answered. Ordering is `lib/set_orch/fleet/attention.py`; changing it is a
  contract change and is deliberately not folded into the display fix.
- **fixed when:** with PM mode on and a terminal-less agent presented, the content
  area shows that agent's conversation (turns from the log endpoint, or the reason
  the log could not be read — never a blank), verified BY LOOKING at
  `localhost:7400` in the browser, plus a unit test that renders `FleetPm` with a
  terminal-less presented agent and asserts the log rows are there.


## Closed

### B-29 — the terminal's last row is cut in half, and the last row is the status bar

- **state:** closed (see the verification at the end of this entry)
- **reported:** 2026-08-20 by the user, with a screenshot of the enlarged agent
  view — *"a terminal aljan a status rész szétesik"*.
- **measured:** a Playwright sweep of the viewport height against the live
  server, one framework-owned terminal open in the enlarged view. TWO
  independent mechanisms, both of which cut the LAST row and only the last row:

  | viewport | what the measurement says | last row visible |
  |---|---|---|
  | 520 px | `.xterm-screen` is **2 px taller than the host's client box** | 12 / 14 px |
  | 440 px | the card overflows the window by **19 px** | 4 / 14 px |
  | 400 px and below | overflows by 59–99 px | **0 / 14 px** |

  - **The 2 px** is the host's own border. `FitAddon` derives the row count from
    the outer box, so `border` (1 px top + 1 px bottom) is not subtracted: a
    224 px host has a 222 px client box, and 16 rows × 14 px = 224. At heights
    that land just under a row multiple it hands back one row more than fits.
  - **The overflow** is `min-h-[12rem]` on the terminal host meeting
    `overflow: hidden` on the enlarged card. Ancestor walk at 440 px:
    `[data-fleet-terminal]` `clientHeight 180` vs `scrollHeight 228`, inside
    `[data-fleet-enlarged]` `clientHeight 289` vs `scrollHeight 321`,
    `overflow: hidden/hidden`. The page itself cannot scroll to it —
    `document.scrollHeight == innerHeight` — so the rows are not merely below the
    fold, they are unreachable.

- **why it is not cosmetic:** a terminal program puts its status line on its last
  row. Cutting the last row is therefore not "losing a row", it is losing the one
  row that says what the agent is doing and what it is waiting for. And it fails
  in the reassuring direction: the terminal above it looks completely normal.

- **⚠ what a fix must NOT do:** it must not resolve the conflict by making the
  card scroll. That keeps the floor and puts the status bar below a fold the
  reader has to discover — the exact shape `ui-quality.md` forbids, *compaction
  must never hide a failure*. A short terminal is honest; a truncated one is not.
  The floor's own argument does not carry over from `MIN_COLS` either: a narrow
  terminal destroys a layout the program composed for N columns, while a short
  one only means fewer rows and a repaint.

- **fixed when:** at every viewport height in the sweep, the last rendered row is
  fully visible — its full cell height, inside both the host's client box and the
  window — and an e2e test asserts it by measuring rendered pixels, not by
  checking that a fit function ran.

- **fixed / verified 2026-08-20:** `web/tests/e2e/fleet-terminal-fits.spec.ts`,
  against the live server with a framework-owned agent this spec starts and stops
  itself. Two changes in `web/src/components/FleetTerminal.tsx`, and **each was
  mutation-tested separately, because either one alone leaves half the defect**:

  | | before | mutate the flex basis back | mutate the fit check out | both in place |
  |---|---|---|---|---|
  | 520 px | 12/14 px | 14/14 | **12/14 px** | 14/14 |
  | 440 px | 4/14 px | **4/14 px** | 14/14 | 14/14 |
  | 400 px | 0/14 px | **0/14 px** | 14/14 | 14/14 |

  - `refit()` now checks the RESULT of the fit — it measures the rendered
    `.xterm-screen` against the host's client box and drops a row when the fit
    handed back one more than fits. Measured against what was rendered rather
    than recomputed from the box: the cell height is xterm's, and a second copy
    of that arithmetic would be a second place to drift.
  - `flex-1 min-h-[12rem]` became `flex-[1_1_12rem] min-h-0`. The same 12 rem is
    now a *preference* rather than a floor: it still contributes 192 px to a
    content-sized grid card, and it yields in the enlarged card instead of
    pushing the terminal's bottom out of a `overflow: hidden` chain.

  The terminal gets short rather than truncated, which is the point — measured at
  the smallest height in the sweep it still renders 7 rows with the status line
  fully visible. The restore after each mutation was grep-verified, not assumed.

### B-7 — the layout control was overruled by whichever panels happened to be open
- **state:** closed (`038c39e3`)
- **reported:** 2026-08-19 by the user — *"column most itt a második rowt
  változtatta csak hogy hány oszlopot akarok jobb felső kapcsolónál és nem az
  összeset?"*, with a screenshot showing three stacked full-width tiles while 3
  columns was selected.
- **measured:** a tile with an open log or terminal carried `md:col-span-full`
  (`wide`), so with two of three tiles holding something open, choosing three
  columns re-laid out exactly one tile. The rule was there to stop ragged rows —
  obsolete once the rows became uniform.
- **fixed when / verified:** 1900×1100, three agents — choosing 3 gives 3 distinct
  column positions at 449 px each, choosing 2 gives 2 at 678 px.
- **reported together with:** the same message asked for the control to be drawn
  rather than numbered (*"oszlop 1,2,3,4 helyett ikonok kellenek amin látszik hogy
  hogy fog kinézni! layout ikonok"*). Done in the same commit — all four buttons
  render an SVG glyph and no digit, with the count kept in the label and in
  `data-fleet-columns`.


### B-0 — the right-hand panel left 59–73 % of the screen empty, and maximise stopped short of the bottom
- **state:** closed (`c4f4842f`)
- **reported:** 2026-08-19 by the user twice in their own words (*"nem használjuk
  ki a helyet jobb oldalt … azt akarom fixen legyen értelmes ablak mérete az
  agenteknek"*, *"agent maximize nem nyitja ki teljesen az aljáig az ablakot"*),
  and by this session earlier as a screen-review finding that was handed on and
  never done.
- **measured before:** 1900×1100 — content ended at 450 px in an 1100 px panel with
  five agents (59 % empty) and at 292 px with two (73 %); tile heights
  119/127/95/95/111.
- **measured after:** the grid spans 85→1088, `scrollHeight === clientHeight === 1003`
  (no gap), three tiles at 498 px each and equal; maximised card 85→1088 with the
  remaining 12 px being the panel's own padding.
- **the cause, for the next reader:** the panel was `overflow-y-auto`, so it had no
  height to give, and every tile sized itself from its own text while the terminal
  took a guessed `62vh`.
