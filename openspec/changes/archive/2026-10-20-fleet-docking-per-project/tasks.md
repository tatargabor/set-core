# Tasks

All tasks are done — the change was implemented and verified on 2026-08-20, and
is written up here because it changes a contract (CLAUDE.md: a change to a
contract carries a spec delta).

## 1. The store

- [x] 1.1 `docks` normalises to a map keyed by project; an empty list stores no
  key at all, so "nothing docked here" and "never docked here" cannot drift
- [x] 1.2 `save_docks` requires `project` and replaces only that key
- [x] 1.3 A pre-change flat list lands in `docks_legacy`, verbatim, and survives
  every later write
- [x] 1.4 `apply_to` hands the client the map, unjoined

## 2. The route

- [x] 2.1 `DocksBody` carries `project`, with no default
- [x] 2.2 A blank project is a 400 and writes nothing
- [x] 2.3 The whole-document `PUT` takes the map shape; a flat list is refused
  rather than re-keyed into a project nobody chose

## 3. The screen

- [x] 3.1 `loadDocks` reads the map; a flat answer reads as nothing docked
- [x] 3.2 `saveDocks` sends the project and refuses to write without one
- [x] 3.3 Fleet renders `docksFor(map, selected)` — the selected project's
  docking and nothing else
- [x] 3.4 Docking and collapsing write only the selected project's key

## 4. Evidence

- [x] 4.1 Store tests: per-project isolation, key removal on undock, a refused
  projectless write, legacy preservation (`tests/unit/test_fleet_layout.py`)
- [x] 4.2 Route tests: the 400, and the project named back in the answer
  (`tests/unit/test_fleet_api.py`)
- [x] 4.3 Surface regression test: another project's dock does not render, and a
  legacy flat list renders nothing (`web/tests/unit/fleetDockingSurface.test.tsx`)
- [x] 4.4 Mutation check: `docksFor` made project-blind → the regression test
  fails (1 failed / 13 passed); restored and re-grepped → 14 passed
- [x] 4.5 Looked at the screen (ui-quality.md): docked a panel in one project,
  switched to another, band absent there, present on return; the store held
  `{"<project>": [...]}`; undocked and the key was gone
