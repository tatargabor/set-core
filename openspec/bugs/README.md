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

## Closed

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
