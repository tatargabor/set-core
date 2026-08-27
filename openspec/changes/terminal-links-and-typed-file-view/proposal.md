## Why

A shell script printed by an agent could not be opened anywhere. The dashboard answered
`could not open <project>/scripts/gates/check-ko-log.sh: executable files are not opened`,
and that refusal is **correct**: it guards `xdg-open`, which would *run* the file. The defect
is that the token reached that route at all — the framework's own file view only ever READS,
so an executable bit means nothing to it.

Measured before proposing, so the change is aimed at the shape of the problem rather than at
the one report. The recogniser (`terminalTarget`, `fileReference`, `desktopReference`) was
run — the shipped code, transpiled, not reimplemented — over **30 real session transcripts**
(5 707 assistant lines, 67 879 lines of tool output, 11 596 distinct path-shaped tokens), and
every verdict was checked against the filesystem:

| what the dashboard does today | measured |
|---|---|
| hands to the desktop, and the path exists | **823** distinct tokens |
| … of those, a **text file** the internal viewer could have shown | **329** (125 under a registered project root) |
| … of those, text **with an executable bit** — refused at both ends | **12** |
| … of those, a **directory** | 431 (209 under a registered project root) |
| … of those, a **binary** file (PNG, MP4, `.pyc`, ELF) | 59 |
| renders a link that does not resolve | **1 744** distinct tokens / 3 975 occurrences |
| … of those, a single-segment `/word` — a web route, a slash command, a component name | **395** / 1 464 occurrences |
| names a file that EXISTS and is nonetheless left as plain text | **249** distinct tokens |

Three failures, and they fail in different directions:

- **A file the framework may read is sent somewhere that must not read it.** 125 text files
  under a *registered* project root went to `xdg-open` because the recogniser consults one
  checkout — the agent's own — and hands everything else away. The endpoints
  (`files.py:_known_root`) would have served every one of them.
- **The absolute branch applies no shape filter at all**, so `/opsx:ff`, `/dd` and every web
  route in an agent's prose becomes an underlined link that answers *no such file or
  directory*. This is the fail direction that costs the most: it teaches the reader that an
  underline in a terminal is unreliable, which spends the credibility of the real links too.
- **A binary file has no view, only a refusal.** Agents produce screenshots constantly and
  print the path; the panel can only say *not a text file*.

Now, because the register already holds all six (`B-83`…`B-88`, commit `c4c7e6c2`) and each
names the measurement that would prove it fixed.

## What Changes

- **Recognition stops guessing and stops over-claiming.**
  - The absolute branch gets the same shape test the relative branch already has, so a
    single-segment `/word` is prose again. A real absolute path is unaffected.
  - The token cleaner survives what agents actually write: markdown emphasis (`**`), a table
    cell's trailing `|`, and a `~/…` home path (expanded server-side, never guessed at in the
    browser).
  - A relative token that is a unique SUFFIX of exactly one path in the listing resolves to
    it. Ambiguous matches stay text — a wrong file that opens is worse than a link that does
    not.
- **What the internal viewer can open, opens in the internal viewer** — across every
  registered project and worktree, not only the checkout the agent stands in. The desktop
  route keeps exactly what remains: a path under no registered root. **This lifts the
  `terminal-file-links` spec's own OUT OF SCOPE line** (*"References to files of a project
  other than the one the terminal's agent belongs to"*), which is why it is a spec change and
  not a fix.
- **A directory opens in the panel's structure pane** — expanded and scrolled to — instead of
  launching a desktop file manager over the dashboard.
- **The content endpoint answers by TYPE, not only text-or-refusal.** UTF-8 text is served as
  today; a renderable binary is served as bytes with its media type; anything else is a
  refusal that names the type and the size. The executable bit is not consulted, because
  reading is not running.
- **The panel renders what it was given**: text in the editor, an image as an image, a PDF in
  a viewer, and any other binary as a stated type and size with the desktop hand-over still
  offered. Saving is offered for text only.
- The desktop-open endpoint's refusals are **unchanged**. Fewer tokens reach it; none of its
  guards is relaxed.

**Not in this change**, and stated so the next reader does not read it as done: paths broken
across a terminal line wrap (497 distinct tokens exceed 80 columns) stay unrecognised — the
recogniser sees one row at a time, and joining rows is a separate mechanism with its own
failure modes.

## Capabilities

### New Capabilities

None. Every behaviour here belongs to a capability that already exists; adding a fourth would
put the same route in two places.

### Modified Capabilities

- `terminal-file-links`: what counts as a reference (the absolute-branch shape test, markup
  and `~` handling, suffix resolution), and which destination it gets — the file view now
  covers every registered project and worktree, and a directory reaches the structure pane
  instead of the desktop. The capability's OUT OF SCOPE list changes.
- `project-file-access`: the content endpoint gains a typed answer — text, renderable binary
  with a media type, or a refusal naming the type and size — under the same confinement,
  the same `_known_root` verdict and the same size limit.
- `fleet-file-view`: the panel gains a non-text view (image, PDF, stated-type binary), states
  which of the two refusals fired, offers saving only for text, and can reveal a directory.

## Impact

- `web/src/lib/fleetFiles.ts` — `unwrap`, `looksLikePath`, `fileReference`,
  `desktopReference`, `terminalTarget`. Measurable without a browser; this is where most of
  the change's risk is retired.
- `web/src/components/FleetTerminal.tsx` — the link provider is given every known root, not
  one; a directory activation calls the panel rather than the desktop route.
- `web/src/pages/Fleet.tsx` — supplies the registered roots and their listings to the
  terminal, and routes a reveal request into the panel.
- `web/src/components/FleetFileView.tsx` — the `Opened` union gains a binary arm; reveal.
- `lib/set_orch/api/files.py` — `read_file` becomes type-aware; a byte-serving route for
  renderable binaries. `_known_root`, `_confine` and `MAX_BYTES` are untouched.
- `lib/set_orch/api/desktop.py` — **unchanged**.
- Depends on `fleet-open-external-path`, whose requirements this change modifies and which is
  not yet archived. That change must archive first, or its deltas and these will disagree
  about what the base said.
