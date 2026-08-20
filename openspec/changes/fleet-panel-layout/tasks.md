<!--
GROUPS 1–3 ARE ALREADY DONE — shipped in `797f7af5` before this change existed.
They are checked and carry their evidence, because that commit changed a contract
(a new route, a new stored field) and this repository routes such changes through
OpenSpec. Documenting it retroactively is the stated repair; it is not a
precedent for skipping the artifact.

Everything from group 4 onward is unbuilt.
-->

## 1. The stored position — server side

- [x] 1.1 Add `splits` to the stored layout document and to `EMPTY`, so a reader
      of an old file gets an empty map rather than a missing key
      [REQ: a-divider-position-is-stored-durably-per-user-on-the-server]
      — `lib/set_orch/fleet/layout.py`; `test_a_divider_position_survives_a_round_trip`
- [x] 1.2 Normalise `splits` explicitly, dropping any value that is not a usable
      number instead of coercing it [REQ: an-absent-position-is-a-default-never-a-zero]
      — `_normalise_splits`; `test_a_divider_nobody_dragged_is_absent_rather_than_zero`
- [x] 1.3 Clamp a stored position into the recoverable range rather than storing
      an ungrabbable edge [REQ: an-absent-position-is-a-default-never-a-zero]
      — `MIN_SPLIT`/`MAX_SPLIT`; `test_a_position_outside_the_recoverable_range_is_clamped_not_stored`
- [x] 1.4 Write positions through `save_splits`, which does NOT bump the
      arrangement's version [REQ: storing-a-divider-position-does-not-disturb-the-arrangement]
      — `test_storing_a_divider_does_not_bump_the_arrangements_version`
- [x] 1.5 Preserve stored positions when a caller replaces the arrangement
      without mentioning them, while an explicit empty map still clears
      [REQ: storing-a-divider-position-does-not-disturb-the-arrangement]
      — `test_saving_the_arrangement_does_not_wipe_dividers_it_never_mentioned`,
      `test_a_caller_that_explicitly_sends_no_dividers_clears_them`
- [x] 1.6 Pass `splits` through `apply_to` unjoined, since a divider has no
      project to be missing from [REQ: a-divider-position-is-stored-durably-per-user-on-the-server]
      — `test_apply_to_passes_dividers_through_unjoined`
- [x] 1.7 Extract the atomic write into one helper so the two writers cannot
      drift [REQ: a-divider-position-is-stored-durably-per-user-on-the-server]
      — `_write_atomically`

## 2. The write route

- [x] 2.1 Add `PUT /api/fleet/layout/splits`, writing positions alone
      [REQ: storing-a-divider-position-does-not-disturb-the-arrangement]
      — `lib/set_orch/api/fleet.py`
- [x] 2.2 Make `splits` on the whole-document body omissible (`None` = leave
      alone) [REQ: storing-a-divider-position-does-not-disturb-the-arrangement]
- [x] 2.3 Verify end-to-end against the running service that a write leaves the
      version and the groups untouched
      [REQ: storing-a-divider-position-does-not-disturb-the-arrangement]
      — measured 2026-08-20: version 31 → 31, 5 groups unchanged

## 3. The divider on screen

- [x] 3.1 Client store: read positions, write them to the divider route, and
      treat an unreadable store as "no positions" rather than an error state
      [REQ: a-divider-position-is-stored-durably-per-user-on-the-server]
      — `web/src/lib/fleetSplits.ts`
- [x] 3.2 Divider component driven by pointer events, measuring each position
      from the drag's origin [REQ: a-panes-edge-is-draggable]
      — `web/src/components/FleetSplitter.tsx`
- [x] 3.3 Ignore movement with no press, and a non-primary button
      [REQ: a-panes-edge-is-draggable]
- [x] 3.4 Keyboard: arrows, Shift for a larger step, Home/End, and a commit on
      every press [REQ: the-divider-is-reachable-without-a-pointer]
- [x] 3.5 ARIA separator role with current/min/max and orientation
      [REQ: the-divider-is-reachable-without-a-pointer]
- [x] 3.6 Write once on release, not per pointer move
      [REQ: a-divider-position-is-stored-durably-per-user-on-the-server]
- [x] 3.7 Both axes and both sides (`grows: before | after`) from the start
      [REQ: a-panes-edge-is-draggable]
- [x] 3.8 Project column width becomes a prop owned by the shell, so the divider
      and the pane cannot disagree about it [REQ: a-panes-edge-is-draggable]
- [x] 3.9 Clamp the client maximum against the measured shell width, leaving the
      agent panel a usable minimum [REQ: an-absent-position-is-a-default-never-a-zero]
- [x] 3.10 Mutation-test the lot: 10 mutants, all caught, restore asserted each
      round [REQ: a-panes-edge-is-draggable]

## 4. A panel has a type

- [x] 4.1 Introduce a panel-type identifier carried by whatever opens a panel,
      and make the agent terminal one type among several rather than the implicit
      whole [REQ: a-panel-declares-its-type]
- [x] 4.2 Render an unrecognised type as unrecognised — named, not blank, and not
      as the type it resembles [REQ: a-panel-declares-its-type]
- [x] 4.3 Test that a stored layout referencing a type this build does not have
      is REPORTED rather than silently dropped, the same way a missing project is
      [REQ: a-panel-declares-its-type]
- [x] 4.4 Check that no type identifier in the layout layer names a domain
      concept — the framework may know "there is a view", never what it lists
      [REQ: a-panel-declares-its-type]

## 5. Docking to an edge

- [x] 5.1 A view instance records which edge it is docked to, or none
      [REQ: a-view-instance-can-be-docked-to-an-edge]
- [x] 5.2 Persist docking in the same document as the arrangement and the
      dividers [REQ: a-view-instance-can-be-docked-to-an-edge]
- [x] 5.3 A docked view renders as a band along its edge, with the shell
      computing the remaining area [REQ: the-agent-grid-fills-what-docking-leaves]
- [x] 5.4 The agent grid lays out inside the remaining area and is told nothing
      about what is docked [REQ: the-agent-grid-fills-what-docking-leaves]
- [x] 5.5 The chosen column count survives docking — three columns stays three
      columns in a narrower area [REQ: the-agent-grid-fills-what-docking-leaves]
- [x] 5.6 Two edges docked at once leaves the grid the intersection of both
      [REQ: the-agent-grid-fills-what-docking-leaves]
- [x] 5.7 Undocking or closing returns the space
      [REQ: a-view-instance-can-be-docked-to-an-edge]
- [x] 5.8 Each docked view's inner edge uses the SAME divider component and the
      same store — no second implementation
      [REQ: a-view-instance-can-be-docked-to-an-edge]

## 6. Docking must not hide a failure

- [x] 6.1 A collapsed docked view holding a failed item marks it on its collapsed
      edge [REQ: docking-must-not-hide-a-failure-silently]
- [x] 6.2 A view that cannot determine what it holds reports not-knowing rather
      than showing no marker [REQ: docking-must-not-hide-a-failure-silently]
- [x] 6.3 Test the marker by MUTATION — remove it and assert the suite fails.
      This is the requirement most likely to be quietly skipped, because a screen
      without it looks finished [REQ: docking-must-not-hide-a-failure-silently]

## 7. Verification

- [x] 7.1 Full web unit suite and the Python fleet tests green
      [REQ: a-view-instance-can-be-docked-to-an-edge]
- [ ] 7.2 LOOK at the screen with a view docked on each of the four edges.
      Structural counts prove it renders; they say nothing about whether it is
      legible [REQ: the-agent-grid-fills-what-docking-leaves]
      ⚠ **NOT DONE, and deliberately left open rather than marked.** Attempted
      2026-08-20 and blocked: the browser extension is not connected
      (`tabs_context_mcp` → "Browser extension is not connected"). Every other
      check in this change is structural or behavioural, and `ui-quality.md`
      states exactly what that leaves unproven — a screen measured as fine had
      a row collapse into a 500px tower, and only a human looking at it caught
      that. So this is the one task whose absence a green suite cannot cover.
- [x] 7.3 Mutation-test the docking geometry, not only the state
      [REQ: the-agent-grid-fills-what-docking-leaves]

## Acceptance Criteria (from spec scenarios)

### fleet-panel-dividers

- [x] AC-1: WHEN a person presses the primary button on a divider and moves the pointer THEN the pane resizes by the distance moved, measured from where the drag began [REQ: a-panes-edge-is-draggable, scenario: the-pane-follows-the-pointer]
- [x] AC-2: WHEN one or more pointer-move events are lost during a drag THEN the next event still resizes to the pointer's actual position [REQ: a-panes-edge-is-draggable, scenario: a-dropped-intermediate-event-does-not-accumulate-error]
- [x] AC-3: WHEN a pointer moves across a divider without a press THEN no resize takes place [REQ: a-panes-edge-is-draggable, scenario: crossing-a-divider-does-not-resize-anything]
- [x] AC-4: WHEN a person presses a non-primary button on a divider THEN no drag begins [REQ: a-panes-edge-is-draggable, scenario: a-non-primary-button-does-not-begin-a-drag]
- [x] AC-5: WHEN a divider has focus and an arrow key along its axis is pressed THEN the pane resizes by a fixed step and the position is persisted [REQ: the-divider-is-reachable-without-a-pointer, scenario: arrow-keys-move-the-divider]
- [x] AC-6: WHEN a person adjusts a divider using only the keyboard THEN the position is stored, despite no release event occurring [REQ: the-divider-is-reachable-without-a-pointer, scenario: a-keyboard-user-is-not-denied-persistence]
- [x] AC-7: WHEN a divider is presented THEN it exposes current, minimum, maximum and orientation to assistive technology [REQ: the-divider-is-reachable-without-a-pointer, scenario: the-position-is-announced]
- [x] AC-8: WHEN a person drags a divider and later reloads THEN the pane renders at the stored position [REQ: a-divider-position-is-stored-durably-per-user-on-the-server, scenario: the-position-survives-a-reload]
- [x] AC-9: WHEN the surface is opened in a second browser on the same machine THEN the stored position applies there too [REQ: a-divider-position-is-stored-durably-per-user-on-the-server, scenario: the-position-is-not-browser-local]
- [x] AC-10: WHEN a person drags across many intermediate positions THEN exactly one write is performed, on release [REQ: a-divider-position-is-stored-durably-per-user-on-the-server, scenario: the-write-happens-once-per-gesture]
- [x] AC-11: WHEN a divider has no stored entry THEN the pane renders at the surface's declared default [REQ: an-absent-position-is-a-default-never-a-zero, scenario: a-divider-that-was-never-dragged]
- [x] AC-12: WHEN the stored document carries a non-numeric value THEN it is treated as absent and the default applies [REQ: an-absent-position-is-a-default-never-a-zero, scenario: a-value-that-is-not-a-number]
- [x] AC-13: WHEN a position outside the renderable range is submitted THEN it is clamped so the edge remains grabbable [REQ: an-absent-position-is-a-default-never-a-zero, scenario: a-pane-cannot-be-stored-into-invisibility]
- [x] AC-14: WHEN a divider position is written THEN groups, parked and unassigned order are unchanged [REQ: storing-a-divider-position-does-not-disturb-the-arrangement, scenario: the-arrangement-is-untouched]
- [x] AC-15: WHEN a divider position is written THEN the arrangement's version is the same before and after [REQ: storing-a-divider-position-does-not-disturb-the-arrangement, scenario: the-guarding-version-does-not-move]
- [x] AC-16: WHEN a client replaces the arrangement without mentioning dividers THEN the stored positions are preserved [REQ: storing-a-divider-position-does-not-disturb-the-arrangement, scenario: saying-nothing-about-dividers-does-not-delete-them]
- [x] AC-17: WHEN a client replaces the arrangement and explicitly supplies an empty set THEN the stored positions are cleared [REQ: storing-a-divider-position-does-not-disturb-the-arrangement, scenario: explicitly-sending-no-dividers-does-clear-them]

### fleet-dockable-views

- [x] AC-18: WHEN an agent session is opened THEN its panel declares the agent type and is laid out as one [REQ: a-panel-declares-its-type, scenario: an-agent-panel-is-one-type-among-several]
- [x] AC-19: WHEN a panel declares an unknown type THEN the screen states it is unrecognised rather than rendering it as another [REQ: a-panel-declares-its-type, scenario: an-unrecognised-type-is-reported-not-rendered-as-another]
- [x] AC-20: WHEN a person docks a view to an edge THEN it occupies a band along that edge and stays across a reload [REQ: a-view-instance-can-be-docked-to-an-edge, scenario: a-view-is-sent-to-an-edge]
- [x] AC-21: WHEN a docked view is undocked or closed THEN its space returns to the agent grid's area [REQ: a-view-instance-can-be-docked-to-an-edge, scenario: undocking-returns-the-space]
- [x] AC-22: WHEN a person drags the divider beside a docked view THEN it resizes and the position is stored by the same mechanism as every other divider [REQ: a-view-instance-can-be-docked-to-an-edge, scenario: a-docked-views-edge-is-draggable]
- [x] AC-23: WHEN a view is docked while the grid has a given column count THEN the grid keeps that count in the smaller area [REQ: the-agent-grid-fills-what-docking-leaves, scenario: the-column-choice-still-means-what-it-said]
- [x] AC-24: WHEN views are docked to two different edges THEN the agent grid fills the area left by both [REQ: the-agent-grid-fills-what-docking-leaves, scenario: docking-on-two-edges-at-once]
- [x] AC-25: WHEN a docked view is collapsed and holds a failed item THEN its collapsed edge carries a marker [REQ: docking-must-not-hide-a-failure-silently, scenario: a-failure-inside-a-collapsed-view-is-marked-outside-it]
- [x] AC-26: WHEN a docked view cannot determine what it holds THEN it reports not-knowing rather than showing no marker [REQ: docking-must-not-hide-a-failure-silently, scenario: a-calm-view-claims-nothing-it-did-not-check]
