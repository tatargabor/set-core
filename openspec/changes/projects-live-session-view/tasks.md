## 1. The model, before any pixel

- [x] 1.1 Add `web/src/lib/projectsView.ts`: one pure function taking `(ProjectInfo[], FleetResponse | null, { view, query })` and returning `{ rows, hiddenByView, hiddenByFilter, totalAll, totalLive, liveMeasured }`. No React, no fetch [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing]
- [x] 1.2 Liveness comes from `FleetProject.agents.length`, keyed by project name — never from `ProjectInfo.status` [REQ: the-live-session-count-shall-be-shown-in-every-view-not-only-the-live-one]
- [x] 1.3 `liveSessions` is `number | null`, with `null` meaning UNMEASURED and reachable only when the fleet result is `null`. A measured zero and an unmeasured cell are separate values all the way to the render [REQ: an-absent-fleet-measurement-shall-be-stated-never-rendered-as-zero]
- [x] 1.4 Fleet projects with live agents and no matching `ProjectInfo` become rows with `registered: false`, present in the live view only [REQ: a-live-project-the-registry-does-not-know-shall-be-shown-and-marked]
- [x] 1.5 The name filter is a case-insensitive substring over the project name, applied in every view, and applied AFTER the view so the two hidden counts are separable [REQ: a-name-filter-shall-narrow-the-rows-in-every-view]
- [x] 1.7 Live counts are SUMMED per name, not assigned. MEASURED in the browser, 2026-08-24:
  `/api/fleet/agents` returned one project twice — the checkout with 5 agents and a worktree of
  it with 0 — and a `Map.set` let the empty entry win, so a project with five live sessions was
  absent from the live view and read `—` in the All view. Held in a test that fails without the
  fix [REQ: the-live-session-count-shall-be-shown-in-every-view-not-only-the-live-one]
- [x] 1.6 `totalAll` / `totalLive` are counted from the data on every call, so the view control can state both sizes without switching [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing]

## 2. Reading the fleet from this screen

- [x] 2.1 Add a typed reader for `GET /api/fleet/agents` to `web/src/lib/api.ts`, reusing `FleetResponse` from `fleetTypes.ts` — no second copy of the shape [REQ: the-live-session-count-shall-be-shown-in-every-view-not-only-the-live-one]
- [x] 2.2 `Manager.tsx` polls projects and fleet on the same 5 s cycle, each tolerating the other's failure; a fleet failure sets `fleet = null` and leaves the listing intact [REQ: an-absent-fleet-measurement-shall-be-stated-never-rendered-as-zero]

## 3. The screen

- [x] 3.1 A view control above the table: `All (n)` / `Live sessions (n)`, defaulting to All on every arrival, with view and query in component state only [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing]
- [x] 3.2 A name filter input beside it, clearable in one action [REQ: a-name-filter-shall-narrow-the-rows-in-every-view]
- [x] 3.3 A live-session column rendered in BOTH views: a count, a dash for a measured zero, and a distinct unmeasured mark carrying its reason in `title` [REQ: the-live-session-count-shall-be-shown-in-every-view-not-only-the-live-one]
- [x] 3.4 Unregistered live rows render with a `not registered` mark and no `Link` [REQ: a-live-project-the-registry-does-not-know-shall-be-shown-and-marked]
- [x] 3.5 A hidden-row line next to the table whenever anything is narrowed, naming the view's share and the filter's share separately, with one control that returns to the unfiltered All view [REQ: rows-the-screen-is-not-showing-shall-be-counted-where-the-reader-is-standing]
- [x] 3.6 An empty result states why it is empty and keeps the clearing control reachable — an empty table must never read as an empty answer [REQ: rows-the-screen-is-not-showing-shall-be-counted-where-the-reader-is-standing]
- [x] 3.7 With the fleet unmeasured, the live view says the measurement is missing instead of rendering an empty list [REQ: an-absent-fleet-measurement-shall-be-stated-never-rendered-as-zero]
- [x] 3.8 Every string added to this screen is English (`uiLanguage` test), and the existing archived-count affordance keeps working [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing]

## 4. Tests that could fail

- [x] 4.1 `web/tests/unit/projectsView.test.ts` — the model: view narrowing, filter narrowing, the two hidden counts separately, and the case where nothing is hidden asserts NO hidden claim is made (the false-absence direction) [REQ: rows-the-screen-is-not-showing-shall-be-counted-where-the-reader-is-standing]
- [x] 4.2 A test that a measured zero and an unmeasured count produce different values, and that `liveSessions: null` is unreachable when the fleet result is present [REQ: an-absent-fleet-measurement-shall-be-stated-never-rendered-as-zero]
- [x] 4.3 A test that an unregistered live project appears in the live view, does not appear in the All view, and carries `registered: false` [REQ: a-live-project-the-registry-does-not-know-shall-be-shown-and-marked]
- [x] 4.4 `web/tests/unit/projectsScreen.test.tsx` — the surface: the control renders both sizes, switching narrows the rendered rows, the unregistered row has no link, and the unmeasured cell is not a zero [REQ: the-live-session-count-shall-be-shown-in-every-view-not-only-the-live-one]
- [x] 4.5 Prove each new test fails without its change — stash-and-rerun per `evidence-discipline`, and record which ones passed either way [REQ: rows-the-screen-is-not-showing-shall-be-counted-where-the-reader-is-standing]
- [x] 4.6 `pnpm test` and `tsc -b` in `web/` are clean against the pre-change baseline (set diff, not a remembered number) [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing]

## 5. Somebody looks at it

- [x] 5.1 `pnpm build` in `web/` so port 7400 serves the change [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing]
- [x] 5.2 DONE, and it earned itself: the look found task 1.7 (a project with 5 live sessions
  missing from the live view) — 904 unit tests were green over it. What is on screen after the
  fix: `All 23 | Live sessions 6`, the filter, and `set-core` reading `Stopped · 154d ago` with
  `10` in the Live column, which is the contradiction this column exists to show. Typing `core`
  in the live view leaves one row and says `25 not shown (20 without a live session, 5 filtered
  out) · show all`. Original 5.2 text: Open `/projects` in the browser and LOOK: the default view, the live view, a typed filter, and the hidden-row line. Say what is on screen, not that it rendered. If the browser cannot be reached, this task stays OPEN and says so [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the projects screen loads THEN the All view is selected and every project the endpoint returned is listed [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing, scenario: the-screen-opens-on-the-full-listing]
- [x] AC-2: WHEN the reader selects the Live sessions view THEN only projects with at least one live agent session are listed [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing, scenario: switching-to-the-live-view-narrows-the-rows]
- [x] AC-3: WHEN the view control is rendered THEN it shows how many rows All holds and how many rows Live sessions holds [REQ: the-projects-screen-shall-offer-a-view-control-defaulting-to-the-full-listing, scenario: each-view-names-its-own-size]
- [x] AC-4: WHEN the reader types text into the filter THEN only rows whose name contains that text, ignoring case, are listed [REQ: a-name-filter-shall-narrow-the-rows-in-every-view, scenario: typing-narrows-the-table]
- [x] AC-5: WHEN the reader has typed a filter and then switches view THEN the filter still applies and the row counts reflect it [REQ: a-name-filter-shall-narrow-the-rows-in-every-view, scenario: the-filter-survives-a-view-switch]
- [x] AC-6: WHEN the reader clears the filter THEN every row of the current view is listed again [REQ: a-name-filter-shall-narrow-the-rows-in-every-view, scenario: clearing-restores-the-view]
- [x] AC-7: WHEN the All view is rendered and the fleet measures three live sessions for a project THEN that project's row shows three live sessions [REQ: the-live-session-count-shall-be-shown-in-every-view-not-only-the-live-one, scenario: a-live-project-shows-its-count-in-the-default-view]
- [x] AC-8: WHEN the fleet measurement arrived and names no session for a project THEN that row shows no live sessions and no unmeasured marker [REQ: the-live-session-count-shall-be-shown-in-every-view-not-only-the-live-one, scenario: a-dormant-project-shows-a-measured-zero]
- [x] AC-9: WHEN the fleet reports a live session for a project absent from the projects endpoint THEN the Live sessions view lists it with its session count and a not-registered mark [REQ: a-live-project-the-registry-does-not-know-shall-be-shown-and-marked, scenario: an-unregistered-live-project-appears-in-the-live-view]
- [x] AC-10: WHEN an unregistered live row is rendered THEN it carries no navigation to a project route [REQ: a-live-project-the-registry-does-not-know-shall-be-shown-and-marked, scenario: the-unregistered-row-is-not-a-link]
- [x] AC-11: WHEN the All view is rendered THEN it lists what the projects endpoint returned, and unregistered live projects are reported by the live view's own count rather than injected [REQ: a-live-project-the-registry-does-not-know-shall-be-shown-and-marked, scenario: the-default-view-is-unchanged-by-it]
- [x] AC-12: WHEN a filter reduces the listed rows THEN the screen states how many rows are hidden by the filter [REQ: rows-the-screen-is-not-showing-shall-be-counted-where-the-reader-is-standing, scenario: a-filter-states-what-it-hid]
- [x] AC-13: WHEN the Live sessions view is selected and projects without a session exist THEN the screen states how many projects are not shown in this view [REQ: rows-the-screen-is-not-showing-shall-be-counted-where-the-reader-is-standing, scenario: a-view-states-what-it-hid]
- [x] AC-14: WHEN rows are hidden by the view, the filter, or both THEN a single control returns the screen to the unfiltered All view [REQ: rows-the-screen-is-not-showing-shall-be-counted-where-the-reader-is-standing, scenario: clearing-is-one-action]
- [x] AC-15: WHEN the fleet measurement cannot be read THEN the screen states that live sessions are unmeasured and each row's cell shows unmeasured rather than zero [REQ: an-absent-fleet-measurement-shall-be-stated-never-rendered-as-zero, scenario: the-fleet-request-fails]
- [x] AC-16: WHEN the fleet measurement cannot be read THEN the All view still lists every project the projects endpoint returned [REQ: an-absent-fleet-measurement-shall-be-stated-never-rendered-as-zero, scenario: the-listing-still-works-without-the-fleet]
- [x] AC-17: WHEN the fleet measurement cannot be read and the reader selects the Live sessions view THEN the view says the measurement is missing rather than showing an empty list [REQ: an-absent-fleet-measurement-shall-be-stated-never-rendered-as-zero, scenario: the-live-view-does-not-claim-calm-it-did-not-measure]
