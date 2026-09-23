## 1. Baseline before anything changes

- [x] 1.1 Record the current web unit-test failure set as a baseline (see the `regression-baseline` skill — a set diff against a baseline you actually ran, never a remembered count) [REQ: every-opener-uses-one-shared-panel-mechanism]
- [x] 1.2 Enumerate the actions each opener offers today and write the list into this file: waiters removal with its confirm (`FleetWaiters.tsx:95-112`), modules preview and install-for-real (`FleetInstall.tsx:136-147`, `:269-277`), restore's footer actions. This list is what step 5 and step 6 are checked against [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist]
- [x] 1.3 Enumerate every `data-fleet-*` marker on the three openers and their rows, and note for each whether a test queries it or asserts its `textContent` — moving a marker is safe only for the former [REQ: every-opener-uses-one-shared-panel-mechanism]

### 1.1 result — baseline, measured 2026-09-23

`npm run test:unit` under node 24 (node 18 fails with `ERR_REQUIRE_ESM`): **7 failed, 1489 passed,
3 failed files of 91**. The failing SET, which is what step 8.2 diffs against — a count cannot
tell a new failure from an inherited one:

```
tests/unit/designDrift.test.ts :: design-system drift carries no arbitrary font size — the scale is 12/14/16
tests/unit/fleetArrangement.test.tsx :: … prints a state it does not recognise as itself rather than as quiet
tests/unit/fleetArrangement.test.tsx :: … renders a waiting agent as waiting, not as quiet
tests/unit/fleetSurface.test.tsx :: a declared block is said once keeps the phase where nothing else on the tile carries the block
tests/unit/fleetSurface.test.tsx :: task 7.12 … names the timeline as absent rather than clickable
tests/unit/fleetSurface.test.tsx :: task 7.4 … costs one click to instruct an unselected agent, and never more
tests/unit/fleetSurface.test.tsx :: task 7.4 … selects back: clicking a tab enlarges that agent instead
```

Full names were captured in a session scratchpad, which does not survive the session — and that
is fine, because a baseline here is **reproducible rather than archived**: re-run the suite three
times and union the failures (the `regression-baseline` skill has the recipe). An absolute path
into somebody's scratchpad is also not something a committed artifact may carry — it leaks the
local layout and is unopenable for every other reader, so it is deliberately not restored here.

**`designDrift.test.ts` is in the baseline and this change writes new markup** — watch that one
specifically; it is already red, so it cannot go redder in a way a count would reveal.

#### CORRECTION — that single-run baseline is not usable. The suite is FLAKY.

Measured immediately after, because a first set-diff claimed this change had *fixed* four
unrelated fleet tests — which it cannot have done, and a result that flatters the change is the
one to distrust. **Four runs of identical code:**

| run | failing |
|---|---|
| baseline | 7 |
| after group 4 | 3 |
| repeat 1 | 5 |
| repeat 2 | 5 |

**Union across runs: 9. Failing in EVERY run: 1.** So **8 of 9 are flaky** — they appear and
vanish without a line of source changing. The only always-red test is
`designDrift.test.ts :: carries no arbitrary font size`.

**What this means for task 8.2, and it is not a detail:** a set diff against ONE run reports
phantom fixes and would equally report phantom regressions. The usable baseline is the **union**
(`baseline/web-unit-flaky-union.txt`, 9 entries) — a failure outside that union is this change's;
one inside it proves nothing either way and must be re-run to tell.

Recorded in the bug register as its own defect: it is not in scope for this change, and a flaky
suite silently degrades every regression check that follows it.

### 1.2 result — every action that must still exist afterwards

| opener | action | source | guard |
|---|---|---|---|
| waiters | `remove (stops the process)` | `FleetWaiters.tsx:106-111` | orphans only |
| waiters | `sure? this stops process {pid}` / `stopping…` | `FleetWaiters.tsx:96-102` | confirm step |
| modules | `preview the install` / `looking…` | `FleetInstall.tsx:270-275` | `dry_run: true` |
| modules | `install for real — writes N file(s) into <root>` | `FleetInstall.tsx:138-145` | second click only |
| restore | `Restore N selected`, `Delete all selected`, `close` | `FleetRestore.tsx` footer | panel-wide |

Restore is the only one with panel-wide actions; the other two are per-row. That is exactly why
only restore gets a footer.

### 1.3 result — markers, and which ones may move

**Must stay on the SAME element** (a test reads that element's own `textContent`, so wrapping it
or adding children changes what the assertion sees):

`data-fleet-waiter` (`fleetInstructSurface.test.tsx:327`), `data-fleet-waiter-remove` (`:337`),
`data-fleet-waiter-confirm` (`:340`), the waiters chip (`:380`), `data-fleet-capability-note`
(`fleetInstall.test.tsx:142`), `data-fleet-install-tense` (`:154`, `:247`),
`data-fleet-install-for-real` (`:241`), `data-fleet-install-refusal` (`:216`).

**Queried only, so may move to a wrapper:** `data-fleet-waiters`, `data-fleet-waiters-orphaned`,
`data-fleet-waiter-status`, `data-fleet-waiter-kept`, `data-fleet-modules`,
`data-fleet-install-panel`, `data-fleet-capability`, `data-fleet-capability-state`,
`data-fleet-install-preview`, `data-fleet-install-report`, `data-fleet-install-changed`,
`data-fleet-install-written`, `data-fleet-install-skipped`, `data-fleet-install-skip-stated`.

**`data-fleet-modules-open`** — written at `FleetInstall.tsx:225`, polled by
`tests/e2e/fleet-install.spec.ts:93`. The shared mechanism must keep emitting it.

**Two whole-container assertions the new chrome must not trip**, and both are easy to break by
adding an innocuous word:
- `fleetInstructSurface.test.tsx:355` — the waiters container must NOT match
  `/remove all|clean up all|remove orphans/i`. A panel footer saying "Delete all" would fail this.
  It is also the structural guard on the no-bulk-removal contract.
- `fleetInstructSurface.test.tsx:369` — when waiters are unmeasured the container must NOT match
  `/none orphaned/`. A panel header that always prints a count would fail this: an unmeasured
  panel must say it is unmeasured, not report zero.

## 2. The shared mechanism, adopted by nobody

- [x] 2.1 Add a disclosure hook owning open state, with an open-state marker contract that every opener emits (the name `data-fleet-modules-open` is already consumed by e2e and must keep working) [REQ: every-opener-uses-one-shared-panel-mechanism]
- [x] 2.2 Add a `Panel` component: overlay positioning, its own stacking context, chrome of icon + title + counts + close, optional footer slot [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist]
- [x] 2.3 Give `Panel` a columns primitive for repeated records, so a body declares fields rather than laying out each row [REQ: a-panel-body-presents-its-rows-as-columns]
- [x] 2.4 Unit-test the mechanism in isolation: open/close, marker emitted, footer present only when actions are passed, and that the panel is not a flow sibling [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else]

## 3. Adopt it where it already overlays

- [x] 3.1 Move `TheRest` (`FleetRestore.tsx:558`) onto the shared mechanism, keeping Escape, backdrop close and click-inside behaviour [REQ: every-opener-uses-one-shared-panel-mechanism]
- [x] 3.2 Run the restore surface tests; any failure here is the abstraction being wrong, not the layout — `TheRest` behaved correctly before this step [REQ: every-opener-uses-one-shared-panel-mechanism]

## 4. Restore panel height follows content

- [x] 4.1 Replace the fixed `70vw × 76vh` with content-driven height up to a maximum; list scrolls past the cap while chrome and footer stay put [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 4.2 Count entries that cannot be restored in the panel header so a scroll can never hide one [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 4.3 Test both directions: one entry gives a short panel; many entries cap and scroll with the chrome fixed [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## 5. Waiters becomes a panel

- [x] 5.1 Replace the in-place body (`FleetWaiters.tsx:195-205`) with the shared panel; no caret on the trigger, since nothing grows any more [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else]
- [x] 5.2 Present rows as columns: process identifier, status, working directory, action [REQ: a-panel-body-presents-its-rows-as-columns]
- [x] 5.3 Preserve the removal action and its confirm step verbatim, checked against the list from 1.2 [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist]
- [x] 5.4 Give the waiters trigger a stable open-state marker — it has none today, and its tests currently find it as "the only button" (`fleetInstructSurface.test.tsx:319`) [REQ: every-opener-uses-one-shared-panel-mechanism]
- [x] 5.5 Assert no action footer is rendered, and that the orphan-only / one-at-a-time / no-bulk contract still holds [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist]

## 6. Modules becomes a panel

- [x] 6.1 Replace the `basis-full` in-place body (`FleetInstall.tsx:233-246`) with the shared panel [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else]
- [x] 6.2 Present rows as columns: module, state, file counts, action [REQ: a-panel-body-presents-its-rows-as-columns]
- [ ] 6.3 Preserve `data-fleet-modules-open`, which `web/tests/e2e/fleet-install.spec.ts:74` polls; run that spec [REQ: every-opener-uses-one-shared-panel-mechanism]
  - **Half done, and left OPEN deliberately.** The attribute is preserved and unit-tested
    (`fleetInstall.test.tsx` — *keeps the open-state marker the e2e spec polls*), and `dist` was
    rebuilt so the dashboard serves this code rather than the 2026-09-21 build.
  - **The spec was NOT run.** It refuses without `E2E_PROJECT=<a registered project with
    completed orchestration>`, and `fleet-install.spec.ts` drives the install path — which
    WRITES FILES into that project's repository. Pointing it at a real consumer tree to tick a
    box is exactly the act the deploy-safety track exists to prevent, and B-144 records that
    even `--dry-run` is not write-free on a fresh tree. Needs a throwaway fixture project and
    the user's say-so, not a guess at which project is safe.
- [x] 6.4 Preserve the two-click preview → install-for-real contract and every report string, checked against 1.2 [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist]
- [x] 6.5 Assert no action footer is rendered [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist]

## 7. Header notices stop being permanently resident

- [x] 7.1 Collapse the two amber state notices (`FleetTerminal.tsx:1194`, `Fleet.tsx:1066`) behind one summary control that states how many it stands for [REQ: compacting-a-notice-hides-its-sentence-never-its-existence]
- [x] 7.2 The summary control stays visible while any collapsed condition holds; opening it renders each sentence verbatim [REQ: compacting-a-notice-hides-its-sentence-never-its-existence]
- [x] 7.3 Make the restore result a floating notice that closes itself when complete and does not when partial [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial]
- [x] 7.4 Group the result's detail: headline, entries that did not start, entries renamed — each its own group in one bounded notice [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial]
- [x] 7.5 Keep failed and skipped counts visible when a group is collapsed [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial]
- [x] 7.6 Reserve the notice strip's height so a notice arriving does not shift the row [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else]
  - **Done by REMOVING the strip, not by padding it out** — and the task's own wording
    turned out to be narrower than its acceptance criterion, which is worth recording
    because it sent the first search in the wrong direction.
  - **What was measured first, on the running dashboard (2026-09-23).** Injecting a notice
    into the project header strip and into the terminal header, then removing it again
    (each probe restored byte-identically, so the measurement is trustworthy):

    | strip | height with / without a notice | positions |
    |---|---|---|
    | project header (`flex-wrap`) | 24 px / 24 px — **never changed** | 5 of 12 children moved, up to 247 px |
    | terminal header | 22 px / 22 px — **never changed** | whole row shifted 287 px (19 px for a bare mark) |

    So **"reserve its height" was already satisfied everywhere and was never the defect.**
    Height is stable because the project path (`truncate`) shrinks to absorb an arrival;
    what actually breaks AC-3 — *nothing already on that row changes position* — is the
    horizontal reflow. A fix aimed at the task's literal wording would have changed nothing
    that was wrong.
  - **The real offender, found by the same method:** the `unasked` notice in `Declared`
    was a row of its own, measured at **1411 × 13 px**, and its arrival pushed the terminal
    below it from **y=150 to y=133 — a 17 px shift** of content the reader was looking at.
  - **The fix**, which the user asked for directly while this was being measured
    (*"The yellow warning triangle icon shouldn'T have a whole line for itself, put it above
    to the icons too. And remove it's description, since when I'm hovering it the default
    description appears"*): the mark moves into the tile's title bar as a non-interactive
    `IconButton` (`TileControls`, `declaredUnasked`), and its duplicate hover panel goes —
    `title` and the accessible name carry the sentence, as they do for every other control.
  - **Verified after the move, same probe, rebuilt `dist`:** rows are `105:22, 133:710`
    **with and without** the mark — `anythingMoved: false`. The 17 px shift is gone, the
    mark is a `SPAN` (a condition, not an act), it sits inside `[data-tile-controls]`, and
    `[data-fleet-declared-note]` count is **0**. Looked at in the browser: amber triangle
    among the icons, no row of its own.
  - **Held by four tests** in `panelMechanism.test.tsx`, two of them mutation-proven
    (adding `onClick` → the not-a-button test fails; emptying the label → the one-description
    test fails; each broke exactly one test, and the restore was byte-identical with 18/18
    green). jsdom has no layout, so the pixels stay a browser measurement — deliberately not
    asserted here, per this file's own header.
- [x] 7.7 Keep amber (withheld/unknown) and red (failed) distinct, as `project-status-contract` requires of an unasked command [REQ: compacting-a-notice-hides-its-sentence-never-its-existence]

## 8. Prove it, and look at it

- [x] 8.1 Every frozen literal stays inside exactly one element — grep the touched components for a string split across markup, and confirm the exact-match assertions still pass (`fleetRestoreSurface.test.tsx:233`, `fleetRoster.test.ts:92`) [REQ: every-opener-uses-one-shared-panel-mechanism]
- [x] 8.2 Set-diff the web unit failures against the **UNION** baseline (`baseline/web-unit-flaky-union.txt`, 9 entries over 4 runs) — not the single-run set. A failure OUTSIDE the union is this change's; one inside it proves nothing either way and is re-run to tell. The suite is flaky (B-149: 8 of 9 failures are non-deterministic), so a single-run diff reports phantom fixes and would equally hide a real regression [REQ: every-opener-uses-one-shared-panel-mechanism]
  - **CORRECTION 2026-09-23 — this diff was clean and still missed a real regression this
    change had caused. Registered as B-150.** Three runs of the full suite gave 5, 5 and 7
    failures over 1535 tests; the union was 7 names, every one of them already in the flaky
    union, so the diff said *no failure outside the known set*. That was true and useless.
  - The always-red test is `designDrift :: carries no arbitrary font size`, and its assertion
    is a **set**: `expect(hits(/text-\[\d+px\]/)).toEqual([])`. The set held 7 entries —
    `FleetWirePanel.tsx` ×4 (already at HEAD) and **3 this change had added**:
    `FleetRestore.tsx:191,202` (0 at HEAD) and `Panel.tsx:144` (a new file). A name-level diff
    cannot see them, because the name was already on the failing list. Note that §1.1 above
    predicted this exact trap in writing — *"it is already red, so it cannot go redder in a
    way a count would reveal"* — and the check that was then run was still a name-level one.
  - **Fixed in this change:** all three are now `text-xs`, so the change adds nothing to that
    hit set. The 4 `FleetWirePanel` hits are pre-existing debt and stay out of scope.
  - **The rule this yields:** when a change touches a file named in a RED collection
    assertion, diff that assertion's own output before and after — the test's pass/fail bit
    is a summary, and its hit set is the measurement.
- [x] 8.3 Prove the no-push requirement by measuring rather than by eye: assert the header's height and a sibling control's position are identical with each panel closed and open [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else]
- [x] 8.4 Stash-and-rerun the tests written for 8.3 and 4.3 — a test that passes without the fix proves nothing (see the `evidence-discipline` skill) [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else]
- [x] 8.5 **Visual check in the browser** against the running dashboard: open each of the three panels, confirm nothing moves, and confirm each panel's rows read as columns. If the browser cannot be reached, leave this task OPEN and say so in the commit and to the user — a green suite does not imply it [REQ: a-panel-body-presents-its-rows-as-columns]
- [x] 8.6 Repeat 8.5 at a narrow window width where the header row wraps, which is where panel anchoring is most likely to be wrong [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN the reader opens the waiters panel THEN the header row's height is unchanged and every other control stays at the same position [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else, scenario: opening-a-panel-leaves-the-header-unchanged]
- [ ] AC-2: WHEN the reader opens the set-core modules panel THEN the content below the header does not move [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else, scenario: opening-a-panel-does-not-push-the-page]
- [ ] AC-3: WHEN a notice appears in a strip that was showing none THEN nothing already on that row changes position [REQ: an-opened-panel-never-changes-the-size-or-position-of-anything-else, scenario: a-notice-arriving-does-not-shift-the-row]
- [ ] AC-4: WHEN a further opener is added using the shared mechanism THEN its panel overlays, carries the same chrome and exposes the same open-state marker without further work [REQ: every-opener-uses-one-shared-panel-mechanism, scenario: a-newly-added-opener-behaves-like-the-existing-ones]
- [ ] AC-5: WHEN any opener's panel is open THEN that opener reports its open state through a stable marker [REQ: every-opener-uses-one-shared-panel-mechanism, scenario: open-state-is-addressable-on-every-opener]
- [ ] AC-6: WHEN the restore panel is open THEN it renders its panel-wide actions in a footer alongside the close control [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist, scenario: a-panel-with-panel-wide-actions-renders-a-footer]
- [ ] AC-7: WHEN the waiters or modules panel is open THEN its chrome carries a close control and no action footer [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist, scenario: a-panel-without-panel-wide-actions-renders-only-a-close-control]
- [ ] AC-8: WHEN the waiters panel is open and an orphaned waiter is listed THEN that row still offers its removal action behind its confirmation step [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist, scenario: row-actions-survive-the-move-into-a-panel]
- [ ] AC-9: WHEN the modules panel is open and a module is not fully present THEN that row still offers its preview, and the preview still leads to the separate write action [REQ: panel-chrome-is-uniform-and-a-panel-wide-action-bar-appears-only-where-such-actions-exist, scenario: the-install-action-survives-the-move-into-a-panel]
- [ ] AC-10: WHEN the waiters panel lists more than one waiter THEN each waiter's identifier, status, working directory and action occupy the same column in every row [REQ: a-panel-body-presents-its-rows-as-columns, scenario: waiters-are-presented-as-columns]
- [ ] AC-11: WHEN the modules panel lists the project's modules THEN each module's name, state, file counts and action occupy the same column in every row [REQ: a-panel-body-presents-its-rows-as-columns, scenario: modules-are-presented-as-columns]
- [ ] AC-12: WHEN a restore completes with every entry started THEN its result is shown and then closes without the reader acting [REQ: a-notice-persists-if-it-describes-a-state-and-closes-itself-if-it-describes-an-event, scenario: a-completed-result-closes-itself]
- [ ] AC-13: WHEN a restore completes with any entry not started THEN its result remains until the reader closes it [REQ: a-notice-persists-if-it-describes-a-state-and-closes-itself-if-it-describes-an-event, scenario: a-partial-result-does-not-close-itself]
- [ ] AC-14: WHEN a condition such as an undeclared agent remains true THEN the notice describing it remains available rather than closing itself [REQ: a-notice-persists-if-it-describes-a-state-and-closes-itself-if-it-describes-an-event, scenario: a-state-notice-remains-while-its-condition-holds]
- [ ] AC-15: WHEN two conditions are collapsed behind one control THEN that control is visible and states that it stands for two [REQ: compacting-a-notice-hides-its-sentence-never-its-existence, scenario: the-summary-control-states-how-many-notices-it-holds]
- [ ] AC-16: WHEN a collapsed condition is still true THEN the control that opens it remains on the header [REQ: compacting-a-notice-hides-its-sentence-never-its-existence, scenario: the-summary-control-does-not-disappear-while-a-condition-holds]
- [ ] AC-17: WHEN a notice reports that something could not be determined THEN it is presented distinguishably from one reporting that something failed [REQ: compacting-a-notice-hides-its-sentence-never-its-existence, scenario: a-withheld-condition-is-not-rendered-as-a-failure]
- [ ] AC-18: WHEN a restore reports entries that did not start and entries that were renamed THEN headline, non-started and renamed are separate groups within one bounded notice [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial, scenario: the-result-groups-its-detail-rather-than-running-it-together]
- [ ] AC-19: WHEN a restore completes with every entry started THEN the result is shown and then closes without the reader acting [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial, scenario: a-complete-result-closes-itself]
- [ ] AC-20: WHEN a restore completes with any entry skipped or failed THEN the result remains on screen until the reader closes it [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial, scenario: a-partial-result-stays-until-it-is-closed]
- [ ] AC-21: WHEN entries that did not start are collapsed within the result THEN the count of failed and skipped entries remains visible without opening the group [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial, scenario: a-collapsed-group-still-reports-its-failures]
- [ ] AC-22: WHEN a project's record holds a single recorded entry and the reader opens the list THEN the panel is as tall as its chrome and that entry require [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: one-recorded-entry-gives-a-panel-sized-for-one-entry]
- [ ] AC-23: WHEN the recorded list holds more entries than the maximum height allows THEN the list scrolls while header and action footer stay in place [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: a-long-list-scrolls-without-moving-the-chrome]
- [ ] AC-24: WHEN an entry that cannot be restored lies below the visible part of a scrolling list THEN the panel's header still counts it [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: scrolling-cannot-hide-an-entry-that-cannot-be-restored]

### 8.3 / 8.5 / 8.6 result — measured in a real browser, 2026-09-23

Against the running dashboard on :7400 with `dist` rebuilt from this source (the previous build
was 2026-09-21 — measuring the old bundle would have been a proxy, not the thing).

**The no-push requirement, measured rather than eyeballed.** Opening the set-core modules panel:

| | closed | open |
|---|---|---|
| header row height | 24 px | 24 px |
| sibling chip (waiters) position | (751, 58) | (751, 58) |
| `document.body.scrollHeight` | 872 | 872 |

`getComputedStyle(panel).position` = `fixed`. Same result for the waiters panel (23.99 → 23.99 px).

**8.6 — the wrapped case, which is where anchoring was most likely to be wrong.** The window
manager ignored the resize (viewport stayed 1745 px), so the header was forced to wrap by
constraining its container to 520 px instead. The row went to **two lines (54.8 px)** and opening
the panel still gave 54.8 px, the sibling still at (751, 58), and the panel still inside the
viewport. Worth stating plainly: this exercised the wrap, not a genuinely small window.

**The defect from the reported screenshot, measured.** The recorded-sessions panel holding ONE
entry is now **104 px — 12 % of the viewport**. It was `h-[76vh]` = 76 %, which is where the
~380 px of emptiness under a single row came from.

**Looked at, not just measured:** the modules panel renders as an overlay with its four columns
aligned under their headings; the waiters panel is short and says `measured: no waiter process is
running on this machine` rather than showing an empty table; the amber declaration warning is now
a small ⚠ mark on the panel header instead of a full-width row. Escape closes.
