## 1. The route, documented retroactively

- [x] 1.1 `DELETE /api/fleet/roster/{project}/{key}` — already shipped (`lib/set_orch/api/fleet.py`, `roster.forget`); this change adds its spec, no code [REQ: A recorded entry can be removed from a project's record by key]

## 2. The per-entry surface control

- [x] 2.1 Trash control after the peek toggle in `RecordedEntry`, armed; first click sends nothing [REQ: The surface offers an armed per-entry forget]
- [x] 2.2 Tooltips state the blast radius: record entry removed, transcript on disk stays, nothing running is stopped [REQ: The surface offers an armed per-entry forget]
- [x] 2.3 Tests: armed first click sends nothing; confirmed click sends exactly one DELETE to the entry's route and the record is re-read; cancel sends nothing; route refusal shown in the footer [REQ: The surface offers an armed per-entry forget, A failed forget is shown, never silent]

## 3. Delete all selected

- [x] 3.1 Footer control at the bottom right, drawn only with a non-empty selection, stating the count, armed, disarmed by selection change or dialog close [REQ: The surface offers a delete of the whole selection, armed, stated in count]
- [x] 3.2 Sequential deletes, successful keys unticked, one re-read after the loop, failures collected and shown together [REQ: The surface offers a delete of the whole selection, armed, stated in count, A failed forget is shown, never silent]
- [x] 3.3 Tests: absent with no selection; placement + arming; one DELETE per ticked key with both ticks cleared; partial failure names the failed key, unticks the success, keeps the failure ticked [REQ: The surface offers a delete of the whole selection, armed, stated in count]

## 4. Verification

- [x] 4.1 `vitest run tests/unit/fleetRestoreSurface.test.tsx` — 40 passed (33 pre-existing, 7 new); stash-and-rerun without the component change: the 7 new tests fail, the 33 pass
- [x] 4.2 `tsc -b` clean; eslint clean of NEW findings (3 pre-existing findings left untouched: `set-state-in-effect` in `Peeked`, `react-hooks/purity` `Date.now` in `TheRest`, unused `beforeEach` in the test file)
- [x] 4.3 Visual check in the browser against the LIVE dashboard (port 7400, real roster): dialog, trash placement, footer with `Delete all selected` bottom right, both armed states rendered; every confirm CANCELLED and the roster re-read untouched afterwards
- [x] 4.4 Design alternative recorded: direct (unarmed) delete rejected — the same header-row mis-click that armed the restore control's guard applies to a destroy

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the trash control is clicked once THEN no DELETE is sent and a confirmation naming the entry is shown [REQ: The surface offers an armed per-entry forget, scenario: the-first-click-deletes-nothing]
- [x] AC-2: WHEN the confirmation is accepted THEN exactly one DELETE is sent to that entry's route and the project's record is re-read [REQ: The surface offers an armed per-entry forget, scenario: the-confirmed-click-forgets-the-entry]
- [x] AC-3: WHEN the dialog is open with nothing ticked THEN no delete-selection control is drawn [REQ: The surface offers a delete of the whole selection, armed, stated in count, scenario: no-selection-draws-no-bulk-control]
- [x] AC-4: WHEN two entries are ticked and the armed confirmation accepts THEN one DELETE per ticked key is sent and both ticks clear [REQ: The surface offers a delete of the whole selection, armed, stated in count, scenario: the-confirmed-bulk-delete-removes-every-ticked-entry]
- [x] AC-5: WHEN a bulk delete partially fails THEN the failure is named, the success unticks, the failure stays ticked, and the record is re-read for the success [REQ: The surface offers a delete of the whole selection, armed, stated in count, scenario: a-partial-failure-is-visible-and-still-refreshes]
- [x] AC-6: WHEN a delete answers non-2xx THEN the reason is shown and the entry remains listed [REQ: A failed forget is shown, never silent, scenario: the-route-refuses]
