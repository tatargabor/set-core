## 1. The dialog

- [x] 1.1 The recorded list opens as a dialog over the page, using the house pattern (`role="dialog"`, `aria-modal`, backdrop) rather than a second one invented here [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 1.2 Three ways out: an explicit close control, Escape, and a click on the backdrop; a click inside does not close it [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 1.3 The restore act moves into the dialog's footer, so the list and the act it feeds stay together [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## 2. Tests and a look

- [x] 2.1 Vitest for each exit — the close control, Escape, the backdrop — and for a click inside NOT closing it [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 2.2 The Escape test asserts the dialog is PRESENT before pressing Escape: without that it passes on a build with no dialog at all, which is a dead test wearing a passing one's clothes (found by running it against the previous build) [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 2.3 Proved: 4 of the 5 new tests fail without the change; the fifth is a carry-over control and is marked as one [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 2.4 LOOKED at it in the browser on the running dashboard: the dialog reads `Recorded in set-core, not open · 47 conversations · 31 agents` with an `×`, the lineages scroll inside it, a peek now renders as a paragraph across the dialog's width instead of through a letterbox, and all three exits were exercised live [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the reader opens the recorded list THEN it opens as a dialog over the page rather than inside the row that triggered it [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: the-recorded-list-opens-as-a-dialog]
- [x] AC-2: WHEN the recorded list is open THEN it can be closed by an explicit close control, by Escape, and by a click on the backdrop [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: the-recorded-list-can-be-closed-three-ways]
- [x] AC-3: WHEN the reader clicks inside the open list THEN it stays open [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: a-click-inside-the-list-does-not-throw-the-reader-out]
