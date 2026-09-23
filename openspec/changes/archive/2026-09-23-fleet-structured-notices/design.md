## Context

The fleet project header is inline JSX at `web/src/pages/Fleet.tsx:3693–3950` — a
`flex-wrap` row, not a component. Four chips in it open something, and each was built
independently: `TheRest` (`FleetRestore.tsx:558`) overlays correctly, while `FleetWaiters`
(`:195`) and `FleetInstall` (`:233`, with `basis-full`) open **in place** and therefore grow the
row and push the page.

Facts that shape every decision below, all measured rather than assumed:

1. **No shared disclosure helper exists.** Each expander owns a `useState(false)`. `Chip`
   (`Chip.tsx:53`) renders the trigger and holds no open state. So this is a new abstraction.
2. **Neither "information-only" panel is information-only.** `FleetWaiters.tsx:111` stops a
   process behind a confirm; `FleetInstall.tsx:136` writes files into the project's repo behind a
   preview. This was the request's one wrong premise and it is the one that could cause damage.
3. **The house overlay already exists** — `TheRest`'s dialog, with Escape and backdrop close.
   There is a pattern to adopt, not one to invent.
4. **The tests address this UI through strings and markers, never structure**, which makes them a
   usable regression detector — but only while the wording stays frozen.

## Goals / Non-Goals

**Goals:**

- Opening anything never changes the size of anything else.
- One mechanism, so a fifth opener cannot invent a sixth behaviour.
- A panel's chrome is uniform; only its body differs.
- A compacted fact stays counted where the reader is standing.
- Every existing action and every consumed `data-*` marker survives.

**Non-Goals:**

- No wording changes.
- No change to what any action does — not the waiter removal, not the install.
- Not the across-projects result, not `FollowPanel`, not the scattered colour literals.
- No new dependency; Tailwind utilities and the existing `index.css` tokens only.

## Decisions

### 1. A `useDisclosure`-style hook plus a `Panel` component, with `Chip` as the trigger

The shared thing is **open state plus positioning**, not markup. `Chip` already renders every
trigger, so the hook hangs off the call site and `Chip` gains the `data-*-open` marker it only
emits for modules today.

*Alternative considered:* put open state inside `Chip`. Rejected — `Chip` is also used for
non-opening facts (counts, labels), and giving every chip an open state would make "is this
clickable?" ambiguous at the call site.

### 2. The panel is positioned, not flowed — and this is the whole point

`position: fixed` (or absolute against a positioned ancestor) with a `z-index`, anchored to its
trigger. It must not be a sibling in the `flex-wrap` row, because anything in that row
participates in sizing and the row is what wraps.

The failure being fixed is not ugliness: a layout that reflows on open moves the control the
reader was about to click, **every time** the control is used. `FleetInstall`'s `basis-full` is the
extreme case — it deliberately claims a whole new wrapped line.

### 3. Uniform chrome, divergent bodies — and row actions are NOT chrome

Chrome: icon, title, counts, close. Restore additionally renders a **footer** of panel-wide
actions (`Restore N selected`, `Delete all selected`) because it has panel-wide actions. Waiters
and modules have none, so their chrome is the close alone — which is what the request asked for,
read correctly.

**Their per-row actions stay.** `remove (stops the process)` and `preview the install` /
`install for real` live in the body. Removing them would delete a capability, and one of them is a
write path into a consumer tree — the class of thing this repository spent nine commits sealing.
A panel that looks tidier by losing a guarded destructive action is a regression, not a cleanup.

### 4. State versus event decides persistence

- A **state** is true right now — the mouse is captured, the agent has not declared itself. It
  collapses behind a badge, and the badge stays while the condition holds.
- An **event** describes something finished — `All 1 restored.`. It floats and closes itself
  after 10 s.
- **A failure is neither.** A partial result does not auto-close, and no badge disappears while
  its condition holds. An overlay may hide a *sentence*; it may never hide a *fact*.

That last line is `ui-quality.md`'s compaction rule applied to overlays, and it is the only place
this design deliberately does less compacting than asked.

### 5. The restore panel's height follows its content, up to a cap

Fixed `76vh` is why one entry sits above 380 px of void. Height becomes content-driven with a
maximum; past it the list scrolls while header and footer stay put. A reason that blocks a
restore becomes a marked row **and** is counted in the header, so the cap can never hide it.

### 6. A frozen literal stays inside exactly one element

Not style — testability. `getByText('All 1 restored.')` matches one element's normalized text, so
inserting markup mid-string splits it across text nodes and breaks the assertion **with no content
lost**, destroying the regression signal this change depends on. Wrap a literal; never interleave
it. Markers and counts sit beside the string's element.

### 7. Markers move only after checking how each is read

`data-fleet-modules-open` is consumed by `web/tests/e2e/fleet-install.spec.ts:74` and must be
emitted by the shared mechanism for every opener, waiters included — it currently has no stable
selector at all (`fleetInstructSurface.test.tsx:319` finds "the only button"). Moving a marker onto
a new wrapper is fine for a test that queries it and then looks inside; it is **not** fine for one
asserting that element's own `textContent`. Each is checked before it moves.

### 8. `IconButton`'s tone vocabulary is reconciled, not replaced

`TileControls.tsx:62` already takes `tone: 'default' | 'amber' | 'ghost'`, and its comment states
the rule this design is built on: a state needing action must be visible without hovering, with the
tooltip holding the reason and never the alarm. `ghost` means "not ours to act on", which the
amber/emerald/red/blue contract in `index.css:84–90` has no word for. Decide it when the tone
helper is written — either `ghost` joins the contract, or it stays a local variant and says so.
Leaving both unexamined and calling the tone single-sourced is the one outcome that is wrong.

## Risks / Trade-offs

- **A restructure can drop content while every structural count still passes** → frozen wording is
  the detector. Compare against a baseline actually run; never quote a remembered failure count
  (see the `regression-baseline` skill).
- **Positioning a panel against a wrapping row is fiddly** — the trigger's position changes when
  the row wraps at a narrower width → anchor to the trigger element, and check at a narrow window
  in the visual pass.
- **Converting an in-place expander can silently drop a row action** → enumerate the actions of
  `FleetWaiters` and `FleetInstall` before and after, and assert each still renders.
- **A 10 s auto-close could hide a failure** → only `complete` results auto-close; `partial` never
  does. Assert both directions, not just the fading one.
- **The visual check may be unreachable** → then the task stays **open**, is reported as open, and
  a green suite is not allowed to imply it.

## Migration Plan

No data migration, no API change; presentation only.

1. **The hook and `Panel`, adopted by nobody.** Additive — revert is deleting two files.
2. **`TheRest` adopts them.** It already overlays, so this proves the abstraction against working
   behaviour before changing anything that currently pushes.
3. **`FleetWaiters` adopts them** — in-place body becomes a panel; columns; row action preserved.
4. **`FleetInstall` adopts them** — `basis-full` removed; `data-fleet-modules-open` preserved.
5. **Restore panel height** becomes content-driven.
6. **The three header sentences** become badge-plus-panel and a self-closing event notice.
7. **Visual check in the browser**, including at a narrow window where the header row wraps.

Each step is its own commit and leaves the suite green, so rollback is reverting the last one.

## Open Questions

- **Does the panel anchor to its trigger, or to the header bar?** Anchoring to the trigger is
  more precise; anchoring to the bar is more stable when the row wraps. Settle at step 3, with the
  narrow-window case in front of you, rather than on paper.
- **Should the modules panel keep its long report block inline, or behind its own disclosure?** It
  is the biggest body by far. Decide once it is in a panel and its real height is visible.
