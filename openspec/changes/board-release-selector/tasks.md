## 1. Component (module: web)

- [x] 1.1 Read `releasePlanned` defensively; drafts = entries with a readable release name
- [x] 1.2 Selector in the strip header: drafts (with the producer's onBoardCount/total) then "all cards"; default = first draft; reader's choice held in component state
- [x] 1.3 Filter band columns and tray by the draft's on-board membership ids; placement still by each card's own lane; headers unchanged
- [x] 1.4 Off-board items as their own group: reason visible, `openTarget` clickable, never placed into a lane
- [x] 1.5 Filter-explained emptiness claims neither zero nor mismatch (`explainable` on ColumnEmpty)
- [x] 1.6 Draft-view header counts come from the draft's membership per lane, not the whole-board lanes array — the 28-against-1 mismatch read as a bug (user, 2026-08-30); whole-board headers stay in the all-cards view and the strip legend

## 2. Tests (module: web)

- [x] 2.1 Default opens ON the draft; member card shown; non-members hidden; whole-board headers intact
- [x] 2.2 Off-board group: reason visible, openTarget click reaches the page opener
- [x] 2.3 "all cards" restores the unfiltered board and drops the off-board group
- [x] 2.4 No `releasePlanned` — no selector, all cards

## 3. Ship

- [x] 3.1 tsc -b clean; board + surface + file-view suites green (85/85)
- [x] 3.2 Served bundle rebuilt (tsc gate respected the sibling's shared tree)
- [x] 3.3 Visual check on the running dashboard against the live answer
