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

### B-69 — renaming a held agent kills the drain on its terminal, silently and then fatally
- **state:** fixed in the working tree, NOT yet live — the running owner daemon still
  carries the old code (see *fixed when*)
- **reported:** 2026-08-23 by the user — renamed a terminal on the fleet screen and
  *"since then I cannot type into it"*
- **measured:** `journalctl --user -u set-agent-owner`, six seconds apart:

  ```
  16:12:28  fleet owner: renamed <old> to <new> (unit set-agent-<old>.scope, pid … — unchanged)
  16:12:34  fleet owner: terminal of <old> reached EOF after 0 bytes
  ```

  Nothing had ended. `OwnerDaemon._attach_drain` installed the pty reader as
  `loop.add_reader(fd, self._drain, agent.label, fd)`, so the label was baked in at
  start; `AgentOwner.rename` re-keys the map, so the next read asked for a name nobody
  held, `owner.read` raised `OwnerError`, `_drain` caught it as an empty read — and an
  empty read is EOF, so it called `_detach_drain(fd)`. Behavioural proof against
  `HEAD` vs the fix, same input, a rename between the attach and the read:
  `detached: [7] | tail: b''` → `detached: [] | tail: b'after the rename'`.
- **why it matters, and which way it fails:** twice in the reassuring direction. The
  terminal goes SILENT rather than broken — keystrokes still reach the pty (`write` is
  by label and the new label resolves), they simply never echo, so it reads to the
  person as *I cannot type into it*. And an undrained pty fills after about a
  screenful, at which point the agent process BLOCKS on its own output: a rename whose
  entire promise is *the process is untouched* eventually stops it. `_rekey` moved
  every label-keyed store and looked complete; the reader in the event loop is not a
  store, which is the same shape as the fifth write path that was not a file.
- **fixed when:** `_drain` takes the fd only and asks `AgentOwner.label_for_fd(fd)`
  each time, and an `OwnerError` is no longer reported as EOF —
  `tests/unit/test_fleet_ownerd.py::test_a_rename_does_not_end_the_drain`. **Live only
  after `systemctl --user restart set-agent-owner`,** which drops every pty master this
  owner holds: the agents keep running in their scopes but become orphans, and each one
  costs a `recover` (stop + `--resume`) to get its terminal back. Until that restart,
  do not rename a terminal.

### B-69 — the leakscan hook blocks a LOCAL `git tag`, which is the safety net the scrub procedure requires

- **state:** open
- **reported:** 2026-08-24 by this session, while clearing the 25 findings that were
  blocking a 112-commit push
- **measured:** `bin/set-hook-leakscan:29` — `PUBLISH_RX` is
  `git\s+(?:-[^\s]+\s+|--[^\s]+\s+)*(?:push|tag)(?:\s|$)`, so it fires on any `git tag`.
  The blocked command was `git tag leakscan-backup-20260824 HEAD && … && git filter-branch
  --msg-filter …` — a purely local backup tag followed by the message rewrite that FIXES the
  findings. Re-running the `filter-branch` half alone passed, which isolates the trigger to
  the `git tag`.
- **why it matters, and which way it fails:** it fails in the blocking direction, which is
  the safe one for leaks and the wrong one here — it stands in front of the repair. A local
  tag publishes nothing; only `git push --tags` (or an explicit refspec) does, and that form
  is already caught by the `push` half. Worse, `.claude/rules/release-safety.md` tells the
  operator to take a backup tag before a history rewrite, so the gate blocks the exact step
  its own rule book prescribes — and the gate's message says not to work around it. A guard
  that refuses the documented repair is how a guard earns its way into `--no-verify`, which
  is the failure mode the leakscan's own phone-number docstring already names.
- **fixed when:** a local `git tag` is not treated as publishing — the pattern matches only
  tag forms that reach a remote (`git push … --tags`, `git push <remote> <tag>`), while
  `git tag <name> <ref>`, `git tag -d`, and `git tag -l` pass. Held by a test that feeds
  `git tag backup-x HEAD` and asserts the hook does not block, alongside the existing
  positive control that `git push --tags` still does.

### B-68 — a review finding's `line` is rendered with an `L` prefix whatever it holds, so prose becomes a line number
- **state:** open
- **reported:** 2026-08-23 by this session, during the required visual check of
  `findings-path-resolvable` on the Learnings screen
- **measured:** dashboard, Learnings tab of a registered project, a HIGH finding rendered
  as `File: /home/.../tests/unit/target.test.ts L(file does not exist)`. The stored value
  is prose the reviewer put on the `LINE:` line, and `web/src/components/LearningsPanel.tsx`
  renders `L{issue.line}` unconditionally. `_parse_review_issues`
  (`lib/set_orch/verifier.py`) takes whatever follows `LINE:` verbatim, with no shape check.
- **why it matters, and which way it fails:** it reads as a location. `L(file does not
  exist)` is a claim about *where* the finding is, made out of a sentence about *whether the
  file exists at all* — and the reassuring direction, because a reader who scrolls past it
  sees a finding that looks located.
- **fixed when:** a `line` that is not a line reference is not rendered as one — either the
  parser rejects a non-numeric `LINE:` value at the point it is stored, or the row renders
  the prefix only for a numeric value. Held by a test that feeds `line: "(file does not
  exist)"` through the row and asserts the `L` prefix is absent.

### B-67 — the restore control runs on the first click, next to `+ start an agent`, and its count is the blast radius
- **state:** fixed in the surface (`<sha>` — this commit); the spec delta is still open
- **reported:** 2026-08-23 by the user, with a screenshot — *"és hiba túl közel van a
  restore gomb és krédezzen rá!!!!!"*
- **measured:** live, on this machine, twice in one hour:
  - the user mis-clicked the control and **21 agents started** on `consumer-app`
    (`journalctl --user -u set-web`: `10:44:02`–`10:44:24`, *"20 started, 15 skipped"*
    then *"1 started, 50 skipped"*), plus 3 on `set-core` at `10:43:51`. Nothing undid
    them except stopping each one by hand.
  - the screenshot shows why: `+ start an agent` and
    `⟳ Restore 21 of 53 — 2 already running, 30 cannot be resumed` sit in the SAME
    header row, a few pixels apart. One is additive and cheap; the other starts
    twenty-one processes that immediately begin reading context.
  - the same shape hit this session minutes earlier: an Enter keypress submitted the
    start form and started an agent nobody asked for.
- **fixed when:** the control asks before acting, naming the count and the project, and
  a first click sends NOTHING to the server. Held by
  `web/tests/unit/fleetRestoreSurface.test.tsx` — the assertion is the absence of a
  POST, not the presence of a dialog, because a confirmation that is drawn but not
  obeyed looks identical from the outside. Mutation-checked: reverting to the
  run-on-first-click behaviour fails 8 tests.
- **still open:** the `agent-fleet-restore` spec still describes a control that acts on
  a click, so this behaviour change needs its delta. Also unexamined: whether the same
  one-click exposure exists on `RestoreFromEmpty` and on the column indicator.

### B-66 — `set-list` presents a prunable worktree as a live one, and so does the Worktrees page
- **state:** open
- **reported:** 2026-08-23 by this session, while adding worktree selection to the fleet
  start form (`fleet-start-agent-in-worktree`).
- **measured:** in this repository, same moment:
  - `git worktree list --porcelain` returns **four** entries, and **three** carry
    `prunable gitdir file points to non-existent location` — their directories no
    longer exist.
  - `set-list` prints all four under "Worktrees for ..." with a `Path:` line each,
    with nothing distinguishing the three that are gone.
  - the dashboard's Worktrees page reads `_list_worktrees`, which parsed the
    `worktree`, `HEAD`, `branch` and `bare` lines and **dropped `prunable`** — so a
    vanished worktree parsed identically to a live one.
- **fixed when:** `set-list` marks or omits a prunable entry, and the Worktrees page
  shows it as prunable rather than as live. The parser half is already done
  (`_list_worktrees` now carries `prunable` and `is_main`, with
  `tests/unit/test_worktree_locations.py` holding it); what is open is the two
  surfaces that still render every entry the same way.
- **note:** the fleet start form and its guard already refuse prunable locations, so
  the *startable* path is covered. This entry is about the two surfaces that only
  DISPLAY — which is the false-value class: a value the system no longer stands
  behind, shown next to ones it does.

### B-60 — nothing can be copied out of a terminal: there is no clipboard path, and mouse tracking eats the selection
- **state:** open
- **reported:** 2026-08-22 by the user — *"copy-pase mintha nem mene a terminal
  ablakokban most"*.
- **measured:** live fleet screen, the `set-core-bugfix2` terminal, in the browser:
  - the xterm element's class list is `terminal xterm xterm-dom-renderer-owner-1
    **enable-mouse-events** focus` — the agent's TUI turned mouse tracking on, so a
    plain drag goes to the agent instead of selecting. After a plain drag
    `.xterm-selection` has 0 children and `window.getSelection()` is empty.
  - with **Shift** the selection does happen: after a shift+triple-click the helper
    textarea holds the line and reports `selectionStart=0 selectionEnd=90`, and the
    highlight is visible on screen. So selection is not broken — the ROUTE into and
    out of it is missing.
  - no clipboard addon is installed: `web/package.json` carries `@xterm/addon-fit`
    and `@xterm/addon-web-links` only.
  - `FleetTerminal.tsx` attaches no `attachCustomKeyEventHandler`, so Ctrl+C goes
    through the core — `evaluateKeyboardEvent` → `triggerDataEvent` →
    `preventDefault` — which means it **sends SIGINT and does not copy**. And every
    keystroke clears the selection anyway: in the bundle,
    `this._coreService.onUserInput((()=>{this.hasSelection&&this.clearSelection()}))`.
- ~~**the half that was never broken:** PASTE works and always did.~~ **WRONG, and
  corrected 2026-08-22 the same evening — see B-62.** That measurement delivered a
  synthetic `paste` event, which is a power the harness has and the reader does not.
  A real `Ctrl+V` never pastes: the core sends `\x16` to the pty and calls
  `preventDefault`, so the browser's own paste never starts. Measured with a page
  `keydown`+`paste` probe: `Ctrl+V` → `defaultPrevented: true`, **zero** paste
  events. The half declared safe was the half that was broken, and the wrong claim
  is kept here rather than erased because the DEFECT CLASS is the durable part:
  driving a thing with an API the user does not have measures a different system.
- **fixed when:** after a selection, one documented key (Ctrl+Shift+C) or the
  header's copy control puts the selected text on the clipboard with nothing
  reaching the pty, and the screen SAYS that selecting needs Shift while the agent
  has mouse tracking on.
- **shipped, and what is verified — `76f95def`, partial:** the copy control, the
  Ctrl+Shift+C key, the amber "the agent is reading the mouse" icon and the
  outcome notice are all on screen (LOOKED at, 1517 px), and the control reports
  honestly with nothing selected — `not copied: nothing is selected — hold Shift
  and drag over the text first`. What is **NOT** verified is the copy of a REAL
  selection: browser automation cannot make one. Measured — a synthetic
  shift+drag leaves `.xterm-selection` empty (`had:0` immediately after the drag),
  while a hand-drag paints a highlight. The harness has different powers than the
  hand here, so the last step needs a person: select with Shift held, press
  Ctrl+Shift+C, paste elsewhere. The entry stays open until somebody has.

### B-65 — the panel was doing the copy itself; the browser was going to do it
- **state:** open (fix shipped, browser confirmation outstanding)
- **reported:** 2026-08-23 by the user, third round — *"beillesztés szöveg ment copy még nem"*,
  and then the observation that redirected the whole thing: *"semmi nem jelenik meg es ha eger
  jobb gomb akkor is eltunik a kijeloles de nem masolja"*.
- **why that one sentence is the finding:** the MOUSE fails the same way. Two rounds had been
  spent treating this as a keyboard problem — B-60 picked a key Chrome had already claimed,
  B-64 replaced the clipboard call with a synchronous one. A path that fails for the key AND
  for the right button is not about keys and not about which clipboard API is called. It is
  the panel performing work the browser was going to perform.
- **the cause, and it was in our own fix:** the handler cleared the selection SYNCHRONOUSLY,
  in the keydown, on the reasoning that copying should leave the interrupt one keystroke away.
  Correct about the goal, wrong about the mechanism — the browser copies the selection that
  exists when the event finishes, so clearing it in the handler destroys the very thing being
  copied. Both clipboard APIs were then the only remaining path, and both are refused or hang
  wherever the browser does not consider the document eligible.
- **the fix, and it is the same shape that made paste work:** decline the keystroke and get
  out of the way. Nothing is cleared in the handler. A `copy` listener answers the browser's
  request for the data with the terminal's selection, which is what PROVES a copy happened —
  the announcement hangs off that event rather than off our own call, and it covers the
  context menu as well as the key. The selection is cleared one macrotask later, so the
  interrupt is still one keystroke away. If the browser never asks within 400 ms, the
  clipboard APIs run as a fallback and announce whatever they answer, so **silence is
  structurally impossible** — which is the property that failed in all three rounds.
- **measured:** 7 new tests, 5 of 5 mutants caught (synchronous clear restored, the data not
  set, the fallback firing after a successful copy, the fallback removed entirely, a copy
  event taken while nothing is selected). 852 web tests green, `npx tsc -b` silent.
  One existing test had to CHANGE rather than pass — it demanded the synchronous clear — and
  the reason is recorded in it rather than edited away.
- **NOT verified in a browser, and it cannot be from this session:** the MCP-driven tab is
  structurally `visibilityState: hidden`, where Chrome refuses `execCommand('copy')` outright
  (measured: returned `false`) and stalls `writeText` (measured: 4.7 s, no answer). Whether a
  reader's own visible tab copies is exactly the thing this session cannot press a key in.
- **fixed when:** the reader selects with Shift, presses Ctrl+C, and PASTES THE TEXT SOMEWHERE
  ELSE. A "copied N chars" notice is a claim about the mechanism; three rounds of this entry
  exist because the mechanism was not the thing that was broken.

### B-64 — copying said NOTHING and cleared the selection: the async clipboard write never answers
- **state:** open
- **reported:** 2026-08-23 by the user, testing the B-63 fix — *"tudod mi nem megy? ha innen
  ctrl-c"*, and then the detail that locates it exactly: *"1 és eltűnik a kijelölés"* — no
  message in the header at all, and the selection gone.
- **measured:** those two observations together leave one candidate, and that is why the
  report was worth more than a stack trace. **The selection vanishing proves the handler
  RAN** — `term.clearSelection()` is only called on the copy branch. **The silence proves
  the write never answered** — every settled outcome, success or refusal, renders a notice.
  So the fault is in `navigator.clipboard.writeText`, not in the key handling.
  Corroborating, from this session: the same call did not return in **4.7 s** from a tab
  whose `visibilityState` was `hidden` (`clipboard-write: granted`, `hasFocus: true`), and
  the B-60 commit had already recorded a **45 s** non-return. That measurement alone could
  not have decided it — a hidden tab is a documented reason for Chrome to stall — which is
  why the reader's observation is the evidence and mine is only the corroboration.
- **why the existing 2 s race did not save it:** it turns a hang into a *reported* failure,
  which is the right thing and still leaves the reader unable to copy. A guard that converts
  silence into a message is not a repair for the thing that was silent.
- **the fix, and its shape:** the SYNCHRONOUS `document.execCommand('copy')` runs FIRST,
  inside the keystroke's own transient activation; the async API stays only as a fallback.
  Order is the whole fix — a fallback that runs second cannot rescue a call that never
  settles. Focus is restored to whatever held it, because a copy that moved the keyboard out
  of the terminal would be its own defect.
- **fixed when:** the reader selects with Shift, presses Ctrl+C, and PASTES THE TEXT
  SOMEWHERE ELSE. Nothing short of the paste proves it — a header saying "copied" is a claim
  about the mechanism, and this whole entry exists because the mechanism reported nothing
  while the result was also absent.

### B-63 — the shipped copy key cannot be pressed in Chrome: Ctrl+Shift+C is the browser's own DevTools shortcut
- **state:** open
- **reported:** 2026-08-23 by the user, testing the B-62 fix — *"beillesztes szoveg ment,
  copy terminalrol nem"* and, decisively, *"ctrl shift c pedig elohozza a debug windowt"*.
- **measured:** the reader's own observation is the measurement, and it is the one this
  session could not have made: `Ctrl+Shift+C` opens Chrome's DevTools element inspector.
  That shortcut is handled by the browser BEFORE the page sees the keystroke, so
  `attachCustomKeyEventHandler` — which is what B-60 relied on — never runs. The handler is
  correct; the key is unreachable.
- **what this says about B-60, and it is the durable half:** the copy path was verified by
  asserting that the DECISION function returns `true` for `Ctrl+Shift+C`, and by clicking the
  header's copy control. Both passed, and both were about the mechanism. Nothing in either
  check could see that the reader's finger never reaches the handler — the same class as
  driving a thing with an API the user does not have. **A keyboard shortcut is not verified
  until somebody presses it in the browser the reader uses.**
- **the paste half is CONFIRMED working** by the same round: *"beillesztes szoveg ment"*.
  B-62's text half is therefore verified by the reader, not only by this session.
- **the image half is absent as designed**, not regressed — see B-62 and the
  `terminal-image-paste` change.
- **fixed when:** the reader can copy a selection out of an agent terminal with a key Chrome
  does not claim, pressed in Chrome, with the copied text pasted somewhere else to prove it —
  and the interrupt is still reachable.

### B-62 — Ctrl+V does not paste into an agent terminal, and a clipboard IMAGE has no path at all
- **state:** open
- **reported:** 2026-08-22 by the user — *"ctrl-c és ctrl-v nem mukodik most agent
  terminalban. kepet sem tudo vagolaprol betenni. korabban mind mukodott"*. The
  "previously" is a native terminal emulator, not this panel: the panel has never
  had either path (see the correction on B-60).
- **measured:** live fleet screen, the `set-core-bugfix2` terminal, with a
  capture-phase `keydown` + `paste` probe installed on the document:

  | key | `keydown.defaultPrevented` | `paste` events |
  |---|---|---|
  | `Ctrl+V` | **true** | **0** |
  | `Ctrl+Shift+V` | false | 1 — `types: ["text/plain"]`, the text reaches the pty |

  The cause is in the emulator, not in this repo's code:
  `@xterm/xterm` 6.0.0, `lib/xterm.js` — `evaluateKeyboardEvent` maps a plain
  `Ctrl`+letter to `String.fromCharCode(keyCode-64)`, so `Ctrl+V` becomes `\x16`
  (SYN); `_keyDown` then runs `triggerDataEvent(key)` followed by
  `this.cancel(e,!0)` → `preventDefault()`. The browser's native paste is
  cancelled before it starts. `Ctrl+Shift+V` falls through with no `key`, so
  nothing is cancelled and xterm's own `paste` listener on the helper textarea
  does the work — which is why exactly one of the two works today.
- **the image half is a separate absence, not the same bug:** even the working
  `Ctrl+Shift+V` delivered `types: ["text/plain"]` only, and xterm's paste handler
  reads `clipboardData.getData("text/plain")` and nothing else. A clipboard image
  therefore cannot reach the pty by any key. The agent runs behind a pty on the
  server and has no access to the reader's browser clipboard, so this is a
  capability to be BUILT (accept `image/*` from the paste event, put the bytes
  where the agent can read them, type that path), not a regression to be undone.
  It is a new capability → OpenSpec, not a direct fix.
- **Ctrl+C is deliberate and stays deliberate:** it goes to the pty as SIGINT
  (B-60), copy is `Ctrl+Shift+C`. What the report shows is that the DECISION is
  invisible at the keyboard — the reader presses the key their other terminal
  uses and gets nothing they can see.
- **NOT measured, and it needs a human:** whether `Ctrl+Shift+C` actually reaches
  the clipboard for the reader. `navigator.clipboard.writeText` timed out at 3 s
  from this session — but the tab's `document.visibilityState` was `hidden`
  (`hasFocus: true`, `clipboard-write: granted`), which is a documented reason for
  Chrome to stall it. That is a fact about the measuring tab, not about the
  product, and it must not be written down as one.
- **fixed when:**
  1. `Ctrl+V` on a focused terminal fires exactly one `paste` event and the text
     appears in the agent's prompt — the same probe above going from
     `{defaultPrevented: true, paste: 0}` to `{defaultPrevented: false, paste: 1}`;
  2. and the header says which keys do what, so the Ctrl+C decision is legible
     where the reader is standing rather than only in this file.
- **shipped, and what is verified — `b4d7aa87`, PARTIAL:** the text half is done and
  measured end to end. The custom key handler now declines `Ctrl+V` and
  `Shift+Insert`, which is the whole repair, because xterm consults it before it
  cancels. On the same live terminal after the fix: `Ctrl+V` →
  `defaultPrevented: **false**`, **1** paste event, 17 chars, and the text appeared
  in the agent's prompt. Mutation-checked: removing the one line turns
  `fleetTerminalPasteKey.test.tsx` red, and the restore was grep-verified.
  **The entry stays OPEN for the image half** — that is a capability nobody has
  built, not a line to delete.

### B-61 — an agent tile's header eats 5-6 rows and leaves almost nothing for the content
- **state:** closed 2026-08-22 — LOOKED at on the same three agents (see *state after
  the fix* below: 38 px of header, 333 px of terminal). The entry stays here with its
  evidence; a deleted entry and one that was never written look the same.
- **reported:** 2026-08-22 by the user, with a screenshot — *"a consumer-app 3
  agentjénél alig marad hely a terminal tartalmának mert tul sok helyet elvisz
  felette a heder … sztem 2 sor kellene egy layout/agent fejlécnek összesen"*.
- **measured:** three agent tiles in the screenshot, each carrying above its
  terminal: a title + icon row, a `says:` block of 2-3 lines, an `N file(s):` line,
  an **always-open** `send an instruction …` input row, and then a separate
  `terminal live ✂ >` row — 5-6 rows before the content, while the terminal itself
  gets about 10.
- **fixed when:** the tile header is at most 2 rows; the instruction box is CLOSED
  by default and opens on a control; the agent's own icons sit in the layout icon
  row rather than on a line of their own. Evidence: LOOKING at the same three
  agents, plus the header's measured height in rows.
- **state after the fix:** closed for the header itself — LOOKED at on the SAME
  three agents, 1517 px, two columns. The tile header is now **22 px of title row
  + 16 px of `says:` row = 38 px**, the instruction row measures **0**, and the
  terminal gets **333 px** on every one of the three. What made the rows:
  - the instruction box opens from a control in the title bar. Where an agent
    cannot be instructed at all there is no control and its one-line reason still
    stands where the box would be — otherwise the seat's absence would go unsaid
    and `↳ ?` elsewhere on the tile would be the only trace of it;
  - the focus takes ONE line with the whole sentence in its tooltip, and the file
    NAMES fold into a count on the same row (names in the tooltip). Enlarged, the
    names come back.
- **what was tried and REVERSED, because it crossed from compacting into
  hiding:** standing the whole `says:` block down while the terminal or the log is
  open. It reads well, and it is wrong: the declared focus comes from the
  messaging bus, the log does not carry it, so that row is the only place the fact
  exists. A unit test caught it, not the screen.
- **the icon question, asked and answered:** *"agent ikonjai miért nem épülnek be
  a layout ikonjai alá közvetlen"* was ambiguous, so it was put to the user with
  the two readings drawn out rather than guessed at. The answer — *"igen, egy
  sorba kerüljön a csempe ikonja és a layout ikon"*, resolved to: **the
  terminal's status row moves into the tile's title bar.** The tile had two icon
  rows for one agent, one directly under the other.
  - done with a **portal**, not by lifting state: phase, the attach
    acknowledgement and the copy outcome live in the terminal, and handing them
    to the tile would put a second copy of each somewhere that can disagree with
    the socket. Absent a slot the row still renders in place — a component that
    only draws its header when someone remembers to pass a slot would one day
    render headerless and say nothing.
  - **a defect the LOOKING found, and only the looking:** with the status row
    beside it the title bar's left half ran out of room and dropped `4m ·
    2657090` onto a line of its own — a merge made to save a row gave the row
    back, on exactly the narrow tiles it was meant to help. Fixed by letting that
    half truncate instead of wrap while a terminal shares the line.
  - **measured after, same three agents, three columns, 1517 px:** head 22 px +
    `says:` 16 px = **38 px**, a terminal row of its own measures **0**, and the
    terminal itself is **376 px** (333 before the merge). The cost, stated: the
    name and the branch truncate on a narrow tile — `consumer-app-atne…`, `quiet d…`
    — with the full text in the tooltip.
  - the portal is held by a test that fails without it (measured: removing
    `createPortal` turns it red; the restore was grep-verified).

### B-59 — in a three-column grid the terminal wraps to a few characters per line and stops being readable
- **state:** open
- **reported:** 2026-08-22 by this session, while looking at the fleet screen to
  confirm a rename — not what was being checked, which is why it is worth writing
  down rather than remembering.
- **measured:** LOOKED at, 1568 px viewport, three-column layout. Two tiles render
  their terminal one WORD per line: `gy / ulón / opsx:ff / hange, / s / zólj, / ogy
  / zt / egyem-e`. The prompt line beneath it is legible, so the pane is alive and
  relaying — it is the width that is wrong. A terminal is a fixed-grid device that
  assumes ~80 columns, which is roughly 560 px at this font; a third of 1568 px
  minus the chrome is well under half of that.
- **the shape, which this repo has already paid for once:** the same finding is
  recorded in `fleetDocks.defaultDockSize` — 320 px "was not a smaller terminal, it
  was a broken one". The docked case was fixed by measuring; the GRID case was not,
  so the defect came back through the other door. A per-axis default fixed one
  caller rather than the rule.
- **not caused by the rename work**, and it does not block it: the names, the
  pencil and the state lines all render correctly in the same screenshot.
- **fixed when:** a terminal pane never renders below the width its own emulator
  needs — either the column count refuses to squeeze a tile that holds an open
  terminal, or the terminal says it cannot be shown at this width instead of
  showing a column of syllables. The check is the screenshot: open a terminal in
  the three-column layout and read a line of it.

### B-58 — the durable stores fsync the FILE and not its directory, so a write can vanish in a reboot
- **state:** open
- **reported:** 2026-08-22 by this session, after a hand-made arrangement disappeared.
- **measured:** at 09:52 today `~/.local/share/set-core/fleet-layout.json` contained
  `docks: {"set-core": [{"kind": "agent", "id": "set-core-bugfix", "edge": "right"}]}`
  — read and quoted at the time. It now contains `docks: {}` and its mtime is
  **2026-08-21 23:30:12**, i.e. older than the reading. `last -x reboot` shows two
  further boots today at 10:52 and 10:53. So the version that carried the dock was
  written after 23:30 and is gone, along with its mtime — the shape of a lost
  rename rather than of an overwrite.
- **the mechanism, and it is in both stores:** `layout._write_atomically` and
  `roster._write_atomically` write a temp file, `fsync` the FILE, then `os.replace`.
  The rename itself is a directory operation, and the directory is never fsynced
  (`grep -n "fsync\|os.replace" lib/set_orch/fleet/{layout,roster}.py` → four lines,
  no `O_DIRECTORY` open anywhere). `os.replace` is atomic with respect to readers;
  it is NOT durable across an unclean shutdown until the parent directory's entry
  is flushed.
- **why it matters more than it looks:** these two files exist precisely to survive a
  reboot. The roster is what a restore reads, and it now carries the names a person
  put back by hand — the thing this whole change was for. A write that is atomic but
  not durable is the reassuring kind of wrong: every check passes, the file is
  complete and parsable, and the loss is invisible until someone remembers what was
  there.
- **fixed when:** both writers open the parent directory and `fsync` it after the
  replace. The check: write, then `debugfs`-free but sufficient — kill the machine
  with `echo b > /proc/sysrq-trigger` on a scratch copy of the flow, or at minimum a
  unit test asserting the directory fd is fsynced (the mutation: remove the dir
  fsync and the test fails).

### B-56 — restore reports `started` for a session that has not resumed: it is sitting on a dialog nobody can see
- **state:** open
- **reported:** 2026-08-22 by the user, on two separate fleets — *"van ami
  visszajött de nem terminálban"* and *"consumer-app 6 agentje most állítottam
  vissza, ott egyiket sem tudom szerkeszteni"*.
- **measured:** LOOKED at, 2026-08-22. After a restore, `POST /api/fleet/roster/
  set-core/restore` answered `started: 7`, all `name_source: "restored"`, and
  `GET /api/fleet/agents` reported all 9 `population: "started-here"` with a
  terminal label — so by every check the framework performs, the fleet is back.
  Opening the terminal on `set-core-bb` shows what the process is actually
  doing: *"Resuming the full session will consume a substantial portion of the
  context limits. We recommend resuming from a summary. → 1. Resume from summary
  (recommended). Enter to confirm · Esc to cancel."* The conversation has NOT
  resumed; the process is blocked on a keystroke. Same on `set-core-e2`, and
  `bb`, `4f`, `33` all carry `dialog open` in their state line.
- **and what the tile shows instead:** with the terminal pane closed — which is
  how every tile comes back, because which panes are open is remembered per
  browser and keyed on the label — the tile renders the transcript and the
  sentence *"no input: this session has no seat on the messaging bus"* (B-48).
  So the one place that could take the keystroke is the one thing not on screen,
  and the sentence that IS on screen says, in effect, you cannot write here.
- **why it is not merely B-48 again:** the framework's own report is wrong in the
  reassuring direction. `started` is true of the PROCESS and false of the
  session, which is the mechanism-versus-result split: the check asks "did an
  agent start", the reader asks "is my conversation back". A restore of nine
  that leaves four blocked on an unanswered dialog reads as a complete restore.
- **measured constraint on the fix:** there is no flag that skips it —
  `claude --help` offers `--resume`, `--continue`, `--fork-session`, and nothing
  that pre-answers the summary prompt. And it should not be pre-answered blindly:
  summary-versus-full is a decision about the user's own context, and choosing it
  for them silently discards conversation they may want.
- **fixed when:** a restored agent whose terminal is waiting on a dialog is
  visible AS THAT on the tile — a state the reader can act on, with the terminal
  one click away — and the restore result stops calling such an entry plainly
  `started`. The check: restore a large session, and without opening any panel,
  the screen says it needs an answer.

### B-57 — a runtime roster was committed, and it carries consumer project names and home paths into a PUBLIC repo
- **state:** open — the file is out of the working tree and gitignored (this
  commit), but **it is still in local history** and must be scrubbed before the
  next push.
- **reported:** 2026-08-22 by this session, while writing a handoff — noticed
  because the same mistake was about to be repeated with a second snapshot.
- **measured:** `openspec/changes/archive/2026-08-21-fleet-agent-restore/.roster-before-reboot.json`
  was added in `a7e5b5de` and re-touched by `7a6330a9`. Its `projects` keys are
  five consumer project names plus `/home/tg`, and 15 lines carry absolute home
  paths. `set-leakscan` classifies it `home-path (15) [BLOCKS]` and refuses the
  push, and `git branch -r --contains a7e5b5de` returns EMPTY — so nothing is
  published and the gate is doing its job. That is the only reason this is a
  defect and not an incident.
- **why it happened, which is the reusable half:** the artifact was deliberate
  and its intent was right — a snapshot of the roster taken before the reboot,
  as evidence. What was wrong is that the evidence was RAW RUNTIME DATA. The
  rule this repo already states is that set-core may read a consumer's data and
  must persist nothing derived from it; an evidence file is persistence, and it
  is the shape that feels exempt because it is "just a measurement".
- **fixed when:** `set-leakscan --tree` is clean, and `git log --all -- '*roster-before-reboot.json'`
  returns nothing. The scrub is a history rewrite (`git filter-branch --index-filter`)
  over the 95 unpushed commits — cheap while unpushed, and deliberately NOT done
  in the same breath as this entry: two other sessions are committing in this
  tree right now, and rewriting refs under them is how their work disappears.

### B-55 — eleven commit SHAs cited in the rule book and this register do not exist
- **state:** open
- **reported:** 2026-08-22 by this session, while closing B-49..B-54 — the SHA it had just
  written was checked before being believed, and that check found the others.
- **measured:** every backtick-quoted short SHA in `openspec/bugs/README.md` was resolved
  with `git cat-file -e`. Eleven fail: `038c39e3`, `0b211f2f`, `28ef5ce7`, `387ba8c2`,
  `a2006254`, `ae9706bb`, `bf33e28e`, `c4f4842f`, `e2eb3dab`, `e52ccdc4`, `f64c7554`.
  `ae9706bb` is also cited in `CLAUDE.md`'s shipped-safety-track list. The commit it names
  exists — `git log --all` finds *"separate scaffold from knowledge with `once: true`"*
  dated 2026-07-24 — but under **two** different SHAs (`8e853fba`, `67bdabf2`), neither of
  them the cited one. Same subject, same timestamp, different hash: history was rewritten
  at least once before today and the references were never updated.
- **fixed when:** every SHA cited in the register and in CLAUDE.md resolves. Better: a check
  that fails when one does not, because this class is invisible — a dead SHA reads exactly
  like a live one until somebody types it.
- **⚠ what this session cannot rule out.** While repairing its own leak (a commit message
  carrying three consumer names, rewritten before anything was pushed), this session ran
  `git reflog expire --expire-unreachable=now --all` and `git gc --prune=now --aggressive`.
  That destroys unreachable objects. The duplicate-SHA evidence above says these references
  were stale well before today — but if any of the eleven were unreachable-yet-still-in-the-
  reflog this morning, that gc removed the last handle to them, and **there is now no way to
  measure which**. Recorded as an unknown rather than argued away: the honest state is that
  the references are dead, the cause is probably an older rewrite, and the proof is gone.

### B-53 — the frustration detector inverts delight into anger, and the false label is then injected into later sessions
- **state:** closed (`259ab007` stopped the injection the same hour it was reported; `9f02e096` removed the detector)
- **reported:** 2026-08-21 by the user — *"feltételezem, hogy lehet ártott is valahol"* — and measured the same hour.
- **measured:** `set-memory recall "frustrated" --tags frustration` returns, verbatim:

  ```
  ⚠️ User frustrated (moderate): szuper!!! akkor inditsunk egy futast? ...
  ⚠️ User frustrated (moderate): pont igy akartam!!! akkor viszont ne reseteljunk ...
  ```

  Both are the user being **pleased**. The detector fires on exclamation marks, so
  enthusiasm is stored as anger (`_save_frustration_memory`,
  `lib/set_hooks/events.py:149,502`). It does not stop at storage: over 21 days of
  transcripts (4958 files under `~/.claude/projects`), 187 memory lines were injected
  into sessions and **168 of them (89.8 %) were these frustration records**. Their
  payloads are not knowledge at all — they are raw `<task-notification>` blocks,
  `<cross-session-message>` bodies, agent system prompts, and meeting-transcript
  fragments captured verbatim from whatever prompt was in flight.
  Exactly **one** line in 187 was a reusable project fact.
- **fixed when:** no memory is written with a sentiment label the prompt does not
  support, and no injected memory's body is a harness artifact. Note the harm
  direction: injecting `⚠️ User frustrated` into a fresh, unrelated session tells the
  model the user is angry when they were delighted, and hands it an out-of-context
  instruction as if it were remembered truth. This is worse than an empty injection.
- **also:** the same path persists meeting-transcript content — personal names,
  spoken business detail — into the memory store. That is the carrier
  [External Project Confidentiality](../../CLAUDE.md) names explicitly
  ("session-end extraction saves insights automatically"), and it is not hypothetical
  any more.

### B-54 — the useful citations all trace to the NATIVE file memory, none to shodh
- **state:** closed (the decision it supports is taken and recorded: openspec/changes/remove-shodh-memory, shipped) (evidence entry — it decides B-49..B-53's disposition)
- **reported:** 2026-08-21 by this session, after the user asked whether any read-back
  had ever been useful.
- **measured:** in one project's transcripts the agent cited remembered facts and acted
  on them — a named alert channel, a *fetch-before-allocating-an-id* rule, a pending
  deploy item. Each traces to a hand-written file in that project's native memory
  directory (`project_alerts-channel.md`, `feedback_bug-id-fetch-before-allocate.md`,
  `project_mcp-prod-deploy-pending.md`). Grepping the same three facts across the
  **120 shodh injection blocks** in that project's transcripts returns `0`, `0`, `0`.
  So the two systems ran side by side on the same project, and only one of them
  delivered anything a session used.
- **fixed when:** not a code fix — this entry closes when the decision it supports is
  taken and recorded: the native file memory becomes the framework's memory layer, and
  the shodh hooks stop writing.
- **caution on the method:** the first sweep of this measurement counted `From memory:`
  and reported 13 files. That string is in `CLAUDE.md`, hence in every transcript — the
  measurement was inside the corpus it measured. `rg` also reported `0` for a pattern
  `grep -a` found, because it treats these transcripts as binary. Both wrong answers
  came back clean and confident.

### B-49 — the ONLY memory-injection path in the default hook mode returns nothing, for every query
- **state:** closed (`259ab007` unbound the hooks; `9f02e096`+ removed the code — the proactive path no longer exists)
- **reported:** 2026-08-21 by this session, while auditing whether shodh-memory still earns its place.
- **measured:** `HOOK_MODE` defaults to `lite` (`lib/set_hooks/util.py:157`), and in
  `lite` every PostToolUse/Subagent handler bails at `if HOOK_MODE != "full"`
  (`lib/set_hooks/events.py:210,265,296,318`). That leaves `handle_user_prompt`
  (`events.py:118`) as the one path that can inject, and it feeds
  `proactive_context(query, limit=3)`. Measured on five unrelated queries:

  ```
  proactive=0 recall=3  <- 'fleet rename'
  proactive=0 recall=3  <- 'worktree merge gates'
  proactive=0 recall=3  <- 'e2e playwright gate'
  proactive=0 recall=3  <- 'consumer integration contract'
  proactive=0 recall=3  <- 'memory hook'
  ```

  `set-memory recall` returns relevant hits on the same store and the same words;
  `set-memory proactive` returns `count: 0` with `semantic_threshold: 0.45`. So the
  store is fine and the retrieval used for injection is not. The system's own meter
  agrees — `set-memory metrics` over 7 days: **empty injections 98.6 % (3718 of 3769)**,
  usage rate 0.0 %, 2 explicit citations, 8465 tokens injected across 328 sessions.
- **fixed when:** `set-memory proactive "<any query that recall answers>"` returns a
  non-zero count, and `set-memory metrics` shows the empty-injection rate falling below
  the recall path's. Note the fail direction: an empty injection is indistinguishable
  from "no relevant memory", so nothing has ever reported this.

### B-50 — `set-memory export` prints a valid EMPTY export and exits 0 when it fails
- **state:** closed (`9f02e096` — export is gone with the CLI; the defect was proven in both directions first: with the daemon stopped the same command returned 7885 records where it had returned 0)
- **reported:** 2026-08-21 by this session.
- **measured:** `set-memory export --output <f>` on a store whose own stats say
  `total_memories: 7864` produced
  `{"version":1,"format":"set-memory-export","count":0,"records":[]}`.
  The cause is the fallback on `lib/memory/core.sh:810` —
  `) || { echo '{...count:0,"records":[]}'; return 0; }` — which converts any failure
  into a well-formed empty backup. The failure itself is in
  `~/.local/share/set-core/memory/set-core/set-memory.log`:
  `RuntimeError: Failed to create memory system: Failed to open storage at ".../set-core"`,
  i.e. the export path opens RocksDB directly and loses the single-writer lock to the
  running daemon, so it can never succeed while the daemon is up.
- **fixed when:** export goes through the daemon like `list`/`recall` do, a failure exits
  non-zero instead of printing an empty document, and
  `set-memory export | jq .count` equals `set-memory stats | jq .total_memories`.
  This is the reassuring-empty class: the backup path cannot fail loudly, so a
  zero-record backup has looked like a successful one for an unknown length of time.

### B-51 — `set-memory list --limit N` silently returns `[]` for N ≥ 58
- **state:** closed (`9f02e096` — list is gone with the CLI)
- **reported:** 2026-08-21 by this session.
- **measured:** bisected on the live store —
  `limit=56 -> 56`, `limit=57 -> 57`, `limit=58 -> 0`, `limit=59 -> 0`,
  `limit=100 -> 0`, `limit=8000 -> 0`. Output at 57 is 135 839 bytes and at 56 is
  131 738, so the boundary tracks response SIZE, not count. Exit status is 0 and the
  body is a well-formed `[]`.
- **fixed when:** `set-memory list --limit 8000 | jq length` returns the store's real
  count. Consequence while open: the store cannot be enumerated or audited at all
  beyond 57 records, and the GUI browse dialog reads the same call.

### B-52 — the knowledge graph has been empty through 56 → 7864 memories, so two documented recall modes are placebo
- **state:** closed (`9f02e096` — the graph is gone with the store)
- **reported:** 2026-08-21 by this session; first recorded 2026-02-16 in
  `docs/research/shodh-memory-audit.md` and unchanged since.
- **measured:** `set-memory graph-stats` today →
  `{"node_count": 0, "edge_count": 0, "avg_strength": 0.0, "potentiated_count": 0}`,
  with `set-memory stats` → `total_memories: 7864`. The February audit measured the
  same zeros at 56 memories, so 7808 further writes produced no node and no edge.
  `entities: []` on every record sampled (57 of 57), which is why: NER never runs on
  the CLI write path. Consequence: `--mode causal` and `--mode associative`, which the
  explore and apply skills pass, cannot differ from `--mode semantic` — the audit
  measured all five modes returning identical ids in identical order.
- **fixed when:** `graph-stats` reports a non-zero `node_count` after a `remember`, and
  the five modes stop returning identical result sets for the same query. Until then
  the honest repair is to stop passing the two modes rather than to keep documenting
  them.

### B-48 — a tile whose pty THIS framework holds says "no input", because the only way in it offers is the messaging bus
- **state:** open
- **reported:** 2026-08-21 by the user, after the restore — *"nem tudok a
  sessionökbe írni, mintha nem én nyitottam volna őket set- alól, hanem külső
  agent"*.
- **measured:** LOOKED at, 2026-08-21, tile `set-core-bb`: the header says
  `set-core-bb · waiting for an answer`, and where the input belongs it reads
  *"no input: this session has no seat on the messaging bus"*
  (`web/src/components/FleetInstruct.tsx:200`, reached when `instructable:false`
  and the terminal pane is closed). Yet `GET /api/fleet/agents` reports that same
  agent `population: "started-here", terminal_label: "set-core-bb"` — the
  framework holds its pty. Writing into it works: typed a character into
  `set-core-34`'s terminal from the browser and it arrived at the prompt. So the
  sentence is true about the bus and reads as a statement about the agent.
  6 of the 8 restored sessions have no seat (`sac agents --json` → only
  `set-core#039178b5` and `set-core#115270d4`, both re-enrolled at the restore
  minute), which is why it is the common case rather than an edge one.
- **fixed when:** a tile with a `terminal_label` never renders "no input". It
  names the way in that exists — open the terminal — and, per CLAUDE.md, offers
  ENROLMENT for the bus rather than staying silent about it. A tile with neither
  a seat nor a terminal keeps today's sentence.

### B-45 — the roster records the runtime's DERIVED name, so restore gives back the process and loses the name the user chose
- **state:** closed (`ad08ed86`, change `fleet-agent-identity`). Verified on the
  live record after the service picked up the code: every set-core entry in
  `~/.local/share/set-core/fleet-roster.json` now carries the framework's label
  (`set-core-34`, `set-core-bb`, …) and none carries a runtime-derived name.
  An agent the framework does not hold is recorded with `label: null` rather
  than with the derived name.
- **reported:** 2026-08-21 by the user, after the first real reboot — *"a nevek nem álltak vissza"*.
- **measured:** the owner's log before the reboot names hand-chosen labels —
  `journalctl --user -u set-agent-owner` → `a viewer attached to set-core-bugfix`,
  `set-core-restart`, `consumer-app-tools`. After restore the same log names
  `started set-core-34 … resumed session 039178b5…`. The roster entry for that
  session carries `label: set-core-c6`, which is the runtime's own
  `nameSource: "derived"` name from `~/.claude/sessions/<pid>.json`, not the
  owner's terminal label: `roster._entry_from` (`lib/set_orch/fleet/roster.py:112`)
  reads `agent.name`, and `discovery` fills `name` from `record.get("name")`
  (`lib/set_orch/fleet/discovery.py:311`). The chosen label exists only in
  `OwnerClient().list_agents()[].label`, which the roster never asks.
- **fixed when:** with an agent started under a hand-typed label, the roster entry
  for its session carries THAT label, and after a restore the tab strip shows it.
  Direction that must not be taken: a label the owner does not hold must not be
  invented — an entry whose label is unknown states so rather than filling in a
  derived name.

### B-46 — the displayed name and the terminal label diverge after a resume, and the screen shows one while the framework holds the other
- **state:** closed (`ec614fcb`, change `fleet-agent-identity`). Measured on the
  live endpoint afterwards: every held agent's `name` equals its
  `terminal_label`, the runtime's string moved to `runtime_name`, and the one
  live collision (pid 54272 named `set-core-33` while pid 43704 holds that
  label) no longer reaches the screen — 54272 is now shown as `set-core-2225`,
  its own label. A foreign agent whose runtime name collides with a held label
  is shown with its pid rather than under the other agent's name.
- **reported:** 2026-08-21 by the user, same report as B-45.
- **measured:** `GET /api/fleet/agents` right after the restore —
  `pid=43271 name=set-core-c6 terminal_label=set-core-34`, and seven more like it.
  A resumed session keeps its session id and gets a NEW derived name from the
  runtime, so the roster (which stores `name`) and the owner (which holds `label`)
  answer differently about the same agent from the moment of the resume. Already
  visible as a collision: pid 54272 is *named* `set-core-33` while pid 43704's
  *terminal label* is `set-core-33`.
- **fixed when:** one identity is displayed and it is the one every control keys
  on. `GET /api/fleet/agents` shows no agent whose displayed name is another
  agent's `terminal_label`.

### B-47 — a docked panel survives a reboot by LABEL, and restore recreates no label, so the pane comes back empty
- **state:** open — the mechanism is shipped (`b29e5240`: a rename carries the
  dock AND its stored width; `753021a7`: restore brings an agent back under its
  recorded label), and the unit tests cover both. It stays OPEN because the
  LIVE half is unproven: the owner service still runs pre-rename code, so no
  rename has yet completed on the running fleet, and the existing dock still
  names `set-core-bugfix` — a label lost before any of this existed. It closes
  when a docked agent has been renamed on screen and the panel followed.
- **reported:** 2026-08-21 by the user — *"a jobb oldali agent sem állt be jobb
  oldalra layout szerint (gondolom a neve miatt)"*. Their guess is correct.
- **measured:** `~/.local/share/set-core/fleet-layout.json` →
  `docks: {"set-core": [{"kind":"agent","id":"set-core-bugfix","edge":"right"}]}`,
  while no live agent carries that label (`GET /api/fleet/agents` lists
  `set-core-34/-bb/-e2/-42/-4f/-5c/-33/-2225`). LOOKED at, 2026-08-21: the right
  pane reads *"no running agent with this terminal in set-core — the panel is
  kept, not closed"*. The dock is keyed on `terminal_label`
  (`web/src/pages/Fleet.tsx:1880`), which B-45 does not restore.
- **fixed when:** after a restore of an agent that was docked before, its panel is
  on the same edge. The empty-pane message stays correct for a genuinely absent
  agent — it is the honest half of this, and must not be removed to hide B-45.

### B-35 — the "waiting for a human" count reads its OWN documentation as an open question, on a task that is already done
- **state:** closed (`70fd5577`)
- **reported:** 2026-08-20 by the user, from the screen — *"3 waiting for a human
  felül de ha rákattintok nem ugrik rá az elsőre, vagy ráugrik de az már nem abban
  a státuszban kellene legyen"*.
- **measured:** `GET /api/fleet/agents` →
  `set-core.awaiting = {"decision": ["fleet-view#9.15"], ..., "total": 1}`.
  The source line is `openspec/changes/fleet-view/tasks.md:148`, and it is
  `- [x] 9.15 …` — a task marked DONE, whose text *describes the mechanism*:
  «`connector.mark_awaiting` writes `<!-- awaiting: … -->` into the change's own
  task file». `open_decisions` (`lib/set_orch/fleet/awaiting.py:230`) matches
  `_AWAITING_MARKER` anywhere on the line, so the quoted example is read as a
  live marker.
- **two defects, and the second is the general one:**
  1. **A completed task cannot be awaiting a human.** The checkbox state is not
     read at all — `[x]`, `[ ]` and `[~]` are treated identically.
  2. **A marker quoted inside inline code is read as a marker.** The
     prose-read-as-fact class: the file documenting the mechanism is inside the
     corpus the mechanism scans.
- **the direction:** it INVENTS work. The header sends the reader to a project
  that is not waiting for anything, which is the fastest way to make a
  legitimate signal ignored — and the count is the first number on the screen.
- **fixed when / verified:** `open_decisions` over this repo returns `[]` while a
  fixture with a genuinely open `- [ ] 1.1 … <!-- awaiting: q -->` still returns
  it. Measured after: `GET /api/fleet/agents` → `awaiting: 2`, both consumer-app's
  (`orphaned: ["returns-and-commissions", "driver-photos-storage"]`), and the
  header on screen reads `2 waiting for a human`.
- **the guard:** a test asserts against THIS repository's own
  `openspec/changes`, because the fixture is written by whoever already
  understands the bug — and it was proven able to fire (both strippers removed →
  it fails).

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
  **How a later session checks that they did**, in one command, because "it is in
  the working tree" stops being true at the next rebase:

  ```bash
  cd web && npx vitest run tests/unit/fleetTerminalSurvivesUnknown.test.tsx
  ```

  Green means the call sites arrived. Red — specifically *keeps the pane when
  every agent comes back `unknown`* failing while the three pure-function tests
  pass — means the helpers survived and the wiring did not: look for
  `labelMemory`, the `projects` normalisation, `attachable`'s `null` branch and
  the `offerWithRemembered` call, with `git log -p -- web/src/pages/Fleet.tsx`.
  That split is diagnostic: the pure tests import the library directly, the
  wiring test renders the screen, so which half fails names which half is
  missing.


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

- **state:** closed (`cba66f78` + the wiring commit that follows it) — see the
  verification at the end of this entry
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
- **verified 2026-08-21:** `bin/set-hook-checkout-guard`, registered on both
  `PreToolUse` and `PostToolUse` for the `Bash` matcher, refuses a pathspec-less
  commit that would carry a foreign staged path, refuses `git add -A` / `.` /
  bare `-u` / `git commit -a`, and refuses a bare `git stash` over uncommitted
  work. 50 tests in `tests/unit/test_checkout_guard.py`, all passing.

  The three checks that make that a measurement rather than a claim:

  | check | result |
  |---|---|
  | guard disabled, suite re-run (restore verified byte-for-byte, by copy — not `git stash`) | **15 failed**; with the guard, 50 pass |
  | mutation rounds, `PYTHONDONTWRITEBYTECODE=1`, each pattern asserted unique | every surviving mutant either equivalent or turned into a new test |
  | the hook run from `PATH` against this repository | `git add -A` → exit 2 with the remedy; `ls -la` → exit 0, silent |

  Two real gaps were found by the mutation rounds and closed, **both permissive**:
  `git commit --all` had no test (the `-a` shorthand was caught by a second branch
  that masked it), and a bare `git stash push` read its own subcommand as a
  pathspec and was allowed.

  A third was found by the tests themselves: the hook's top-level filter was
  anchored to the start of a command, so `xargs git add` never entered the guard
  at all.

  **What this does NOT cover, stated because a completeness claim is a
  measurement:** a working-tree modification cannot be attributed to a session by
  this mechanism — file edits do not arrive as shell commands — so the stash
  refusal is unconditional on the command's shape rather than attributed. And the
  index-delta attribution has a race the width of one `git add`, which errs
  permissive; it is commented where it is computed.

### B-34 — the session record's `sessionId` goes stale, so the fleet measures a dead log with `binding_confirmed: true`

- **state:** open
- **reported:** 2026-08-20 by the user, who saw PM mode present an agent whose own
  screen said it was working (*"akkor is odarakta amikor meg dolgozik"*)
- **measured:** pid 113100's record `~/.claude/sessions/113100.json` names
  `sessionId 83de5d69…` with `updatedAt` 12:18:48; the terminal's own status line
  says `e96872a1…`, and on disk `83de5d69….jsonl` is 97 KB last written 21:17:47
  while `e96872a1….jsonl` is 4.4 MB last written 21:32:01 — 75 s before the check.
  The state endpoint reports `binding_confirmed: true` and
  `last_movement_seconds: 902` for a session that moved 75 s ago.
- **the direction that costs:** the binding is confidently wrong rather than
  absent. `_session_log_for()` deliberately has no "newest log in this project"
  fallback (measured 4 correct of 9), so a missing record is reported as missing —
  but a STALE record is not missing, and nothing downstream can tell.
- **why it goes stale:** a session that continues past a compact or a resume opens
  a new transcript under a new id; the per-pid record keeps the id it was written
  with. One record per pid, so there is nothing to disambiguate — the newer id is
  simply never recorded.
- **fixed when:** for every live agent, `state.session_log`'s basename equals the
  session id the process is actually writing, checked against the newest transcript
  that names that pid's cwd — and a record whose named log has not moved while a
  newer one in the same project has is reported as unconfirmed rather than
  confirmed.
- **note:** `fleet-pm-mode` does not depend on this being fixed. Its own filter
  (`who_has_the_floor()`) excludes an agent that owes the next utterance, and both
  logs here fail that test — but that is a second, independent reason, not a repair.

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


### B-36 — an engine call without a change silently burns every pending answer

- **state:** open
- **reported:** 2026-08-21, by an adversarial review of
  `work-cycle-question-outbound`, and **reproduced independently** before entry.
- **measured:** `open_engine(tree, change="")` leaves `tasks_path` as `None`, so
  `_awaiting_keys` returns an empty set (`lib/set_workcycle/cli.py:82-85`). In
  `connector.intake` the guard is `if awaiting_keys and key not in awaiting_keys`
  (`lib/set_workcycle/connector.py:318`) — an empty set is falsy, so the guard is
  skipped and **every** answer is applied and consumption-stamped. Back in
  `cli.py:125` the release is gated on `if tasks_path is not None`, which on that
  path it is not: nothing is cleared, nothing is recorded. The same happens on the
  not-adopted early return, which calls `intake(root)` with no `awaiting` at all
  (`cli.py:102`). Reproduced on a throwaway tree:

  ```
  answer written:            human--20260821T000746.json
  intake(tree)            →  ['applied my-change#3.1 (from human)']
  intake(tree, awaiting=…) →  ['no answers were pending']
  consumed:                  ['human--20260821T000746.json']
  ```

- **why it is severe:** the task stays `- [?]` for ever, the group it holds never
  becomes runnable, and the person's answer is unrecoverable through the normal
  path — while the command **prints `applied …`**. It fails in the reassuring
  direction twice: the operator sees success, and the engine reports a calm it has
  not verified. Any read-only invocation without `--change` is enough.
- **⚠ what a fix must NOT do:** it must not make an empty `awaiting` set mean
  "match everything". The correct reading is "we do not know what is awaited",
  which is not the same as "nothing is awaited" — the false-absence class. Nor may
  it quarantine or delete: the answer belongs where it is until it can be applied.
- **fixed when:** an intake that cannot determine the awaiting set applies nothing
  and consumes nothing; a later call that can determine it applies the answer; and
  a test asserts the FIRST call left the file unconsumed — asserting only that the
  second call works would pass on the broken code too.
- **belongs to:** the code shipped by `work-cycle-engine-apply-first`.

### B-37 — an answer's `source` field reaches the log raw, and it is written off-machine

- **state:** open
- **reported:** 2026-08-21 by an adversarial review.
- **measured:** `cli.py:130-131` logs
  `"released %s — an answer arrived from %s"` with `applied.source` taken verbatim
  from the answer document (`connector.py:303-305`, no validation, no bound).
  `answer_filename` sanitises `source` for the FILENAME (`connector.py:141-152`)
  and nothing sanitises it for the log. Once answers can be written by a party off
  this machine — which is what the question bridge introduces — that is
  arbitrary, unbounded, externally-chosen text in the framework's journal.
- **why it is a defect and not a nit:** the framework's own rule is *shape, counts
  and error classes only* (`lib/set_orch/project_status.py:23`). The enumeration
  missed this field because it names "the question and the answer", and `source`
  is neither — the same shape as the defect that rule's own docstring describes.
- **fixed when:** `source` is bounded and sanitised before it reaches a log line,
  and a test feeds a hostile `source` and asserts what the journal contains.

### B-38 — an answer is interpolated into a full-session prompt as a standing instruction

- **state:** open
- **reported:** 2026-08-21 by an adversarial review, with the security lens.
- **measured:** `lib/set_workcycle/prompt.py:95-101` renders answers as
  `f"- **{task}**: {answer}"` under the heading *"Questions that have been
  answered"*, followed by *"They are decided now — act on them rather than asking
  again."* No fencing, no escaping, no length bound. That string becomes
  `cmd += ["--", prompt]` for `claude -p` running as **a full session** with the
  project's own hooks and permission mode (`lib/set_workcycle/runner.py:60-81`),
  in the project's tree, unattended.
- **why the severity changes now:** today an answer can only be written by
  somebody already on the machine. The question bridge is precisely the mechanism
  that extends that write surface to whoever can post in a chat channel. An answer
  reading *"…also run: …"* is indistinguishable from a decision a person made, and
  every gate and test still passes — the injected instruction IS the work product.
- **fixed when:** answer text is delimited where it lands and bounded in length;
  where the question offered a closed option set, an answer outside that set is
  refused rather than pasted; and a test asserts that an answer containing
  instruction-shaped text does not change what the unit is told to do.
- **belongs to:** the code shipped by `work-cycle-engine-apply-first`; it is a
  precondition for `work-cycle-question-outbound`, not a task inside it.


### B-39 — `mark_awaiting` silently fails on the ordinary file shape, and its failure empties the register

- **state:** open · **⚠ severity: this is the most serious entry in this file**
- **reported:** 2026-08-21 by an adversarial review, **reproduced independently** before entry.
- **measured:** `_task_line_re` (`lib/set_workcycle/connector.py:347`) opens with
  `(?P<indent>\s*)`, and `\s` matches a newline. When a blank line precedes the task —
  **the shape of every `tasks.md` in this repository** — the match starts on that
  newline and the rewrite lands on the wrong line. Reproduced:

  | file | `mark_awaiting` returned | `awaiting_tasks` |
  |---|---|---|
  | blank line before the task | `True` | `[]` |
  | no blank line | `True` | `[('1.1', 'plain question')]` |

  In the first case the comment is written onto the heading line, the blank line is
  eaten, and the task is never marked.

- **why it is the worst one here:** the failure does not stop at the register. With no
  awaiting task, `_awaiting_keys` returns an empty set, and `intake`'s guard is
  `if awaiting_keys and key not in awaiting_keys` — falsy, so **every pending answer for
  any change is applied and stamped consumed**, while `clear_awaiting` fails and nothing
  is recorded. The answer's text is destroyed. This is B-36 reached by a second route,
  and the cycle prints `marked 1.1 as awaiting a person` and then `applied …` while
  neither happened. Reassuring direction, twice.
- **fixed when:** marking a task with a blank line before it produces `- [?]` on that
  task and leaves the blank line alone; `awaiting_tasks` finds it; and a test uses a
  file with a blank line, because the file shape IS the reproducer.

### B-40 — an intake pass that found an already-consumed document reports that it found nothing

- **state:** open
- **reported / reproduced:** 2026-08-21.
- **measured:** `IntakeResult.as_lines()` (`connector.py:187-196`) renders applied,
  unmatched, superseded, deferred and quarantined — `already_consumed` is collected at
  `connector.py:268` and **never rendered**, so the list falls through to its
  `["no answers were pending"]` default. Reproduced: second pass returns
  `already_consumed: ['chat--…json']` and `lines: ['no answers were pending']`.
- **why it matters:** `intake_lines` is the only thing `EngineView` carries out, so this
  is what an operator sees. The dataclass docstring says *"Every category is reported;
  none is silent"* — the comment is false, which is the shape the rules name: a comment
  is a claim, not a measurement.
- **fixed when:** a pass that saw an already-consumed document says so, and a test
  asserts the second pass does not say "no answers were pending".

### B-41 — a superseded answer is applied on the next pass

- **state:** open
- **reported / reproduced:** 2026-08-21.
- **measured:** `intake` stamps only the newest answer as consumed
  (`connector.py:315-325`); the superseded ones are left unconsumed and in place.
  Reproduced: pass 1 → `applied ['MASODIK'] superseded ['ELSO']`; pass 2 →
  `applied ['ELSO']`.
- **why it matters:** the same task asked a second question later becomes awaiting again,
  and the stale answer silently releases it and reaches the next unit's prompt as the
  person's decision. `retained` was meant to mean *kept, not acted on*.
- **fixed when:** a superseded answer is retained and never applied on a later pass, and
  a test runs intake twice.

### B-42 — answer ordering is decided by a field the answer's own author chooses

- **state:** open
- **reported / reproduced:** 2026-08-21.
- **measured:** `connector.py:316` sorts by `(written_at, filename)` and `written_at` is
  read straight off the document (`connector.py:306`). Reproduced: an answer stamped
  `9999-01-01` beat a real one and the real one was reported as
  `superseded — retained, a newer answer won`.
- **why it matters now:** while only somebody at this machine can write an answer this is
  a footgun. `work-cycle-question-outbound` is the change that extends the write surface
  to whoever can post in a chat channel, where "post first with a future date" wins every
  race against the person the question was put to — and the log line states the opposite.
- **fixed when:** ordering uses a time the receiving side observed, or the document's own
  time is bounded to a sane window and the log says which was used.

### B-43 — the question text can write new task lines into the project's task file

- **state:** open
- **reported / reproduced:** 2026-08-21.
- **measured:** the question comes from a unit's verdict, is `.strip()`ed and nothing else
  (`verdict.py:158`), and is embedded in a single-line HTML comment
  (`connector.py:370`). Reproduced with a question containing `-->` and a newline:

  ```
  - [?] 1.1 real <!-- awaiting: ok -->
  - [ ] 9.9 INJEKTALT TASZK -->
  - [ ] 1.2 other
  ```

  `9.9` is now a real, parsed task in that group.
- **why it matters:** the awaiting task is the register every other mechanism derives
  from. A register the unit can forge makes the derivation worthless — and the question
  is also what an outbound would carry to a person, in the unit's words.
- **fixed when:** a question containing a newline or a comment terminator cannot add,
  alter or remove a line, and a test uses exactly those two characters.

### B-44 — `change` and `task` reach a filesystem path unvalidated

- **state:** open
- **reported / reproduced:** 2026-08-21.
- **measured:** `record_answer` interpolates `change` into
  `set/runtime/work-cycle/{change}/answers.jsonl` (`connector.py:421,427`) and
  `open_engine` builds `base / change / "tasks.md"` (`cli.py:112`). Reproduced:
  `record_answer(tree, "../../../ESCAPED", …)` wrote to
  `…/set/runtime/work-cycle/../../../ESCAPED/answers.jsonl`. Both values arrive from
  `--change` / `--task` on `cmd_answer` (`cli.py:563-567`), which is the entry point an
  answer bridge would drive from message text.
- **why the enumeration missed it:** the rule that covers these fields is scoped to log
  lines. The right instrument was aimed at the wrong surface — the question is not only
  *does this field reach a diagnostic* but *where does this field land*.
- **fixed when:** a path built from either field is refused unless it resolves inside the
  tree, and a test passes a traversal in each.


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
