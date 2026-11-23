## 1. Sharing

- [x] 1.1 `bin/set-wave-board`: editor list (`SET_WAVEBOARD_EDITORS` / default path), session account from `.claude.json`, `share_step()`; `init --artifact-url` and `link` print it; `share [<job>...]` command; `--json` carries a `share` object [REQ: the-share-step-names-the-editors-and-the-owner-account] — 2026-11-08: `share_info`/`share_lines`; addresses only on stdout
- [x] 1.2 `bin/set-hook-waveboard`: the refusal paragraph asks the owner account for edit access, no `SET_WAVEBOARD_PUSH=off` advice [REQ: a-refused-push-asks-for-edit-access] — `_owner_account()` reads the same list; the old advice is gone (`grep PUSH=off` in the reason: none)

## 2. Dependencies

- [x] 2.1 `bin/set-wave-board`: `depends_on` validation, `[project:]job/item` parsing, `add --depends-on`, `depend`, `undepend` [REQ: an-item-can-depend-on-another-board-s-item]
- [x] 2.2 Resolution: met only by `done`; unresolved = unmet with a reason [REQ: a-dependency-is-met-only-by-a-done-item-and-never-by-an-unknown-one]
- [x] 2.3 `sync`: `waiting_on` and `blocks` computed into the hashed payload, registry scan without git [REQ: the-payload-carries-what-each-item-waits-on-and-what-it-blocks] — computed fields added only when non-empty, so a board without dependencies hashes as before (test)
- [x] 2.4 `set` guard on `doing`/`done`, `--force` [REQ: a-waiting-item-cannot-be-started-by-report]
- [x] 2.5 `overview [--json]` [REQ: overview-is-the-combined-view-over-every-registered-project]

## 3. Page

- [x] 3.1 `templates/waveboard/page.html`: effective blocked for a waiting todo, waits-on chip, blocks chip; old payloads unchanged [REQ: the-page-shows-waits-on-and-blocks] — the Kanban card had to get `grid-template-columns: minmax(0,1fr)` and the chip wraps instead of truncating: found in the visual check, a long unresolved reason pushed the wave tag out of the card

## 4. Fleet

- [x] 4.1 `lib/set_orch/fleet/waveboards.py` (core): `deps_out`, `deps_in`, `waiting`, `deps_unresolved` over the boards of one read [REQ: the-summary-carries-the-dependency-edges-between-boards]
- [x] 4.2 `web/src/lib/fleetWaves.ts` + `FleetWaves.tsx`: row markers, chip dangling count [REQ: the-rows-and-the-chip-show-the-dependencies]

## 5. Docs and verification

- [x] 5.1 `.claude/skills/set/wave-board/SKILL.md`: sharing (owner account, editors, refused push) and dependencies
- [x] 5.2 Python unit tests for 1.1–2.5 and 4.1; vitest for 4.2; mutation checks on the met rule, the guard and the unresolved-is-unmet rule — `tests/unit/test_wave_board.py` 62 passed (17 new), `tests/unit/test_fleet_waveboards.py` 19 passed (3 new), vitest fleetWaves* 22 passed (4 new + 3 updated for `dangling`). Mutations, all caught with a hashed restore: skipped-counts-as-met (1 fail), no `set` guard (1), unregistered-is-met (1), no dependency view in the payload (3), fleet unknown-is-met (1), hook advises PUSH=off again (2). Full web suite: 2 failures, both in files this change does not touch (`designDrift` flags `FleetWirePanel.tsx`, `fleetTileClick`)
- [x] 5.3 Visual check in Chrome: the fleet's wave list with a dependency, and a rendered board page with waits-on and blocks — 2026-11-08, a second server from this tree on 127.0.0.1:7499 (set-web was not restarted: its cgroup holds a viewer the user opened), two temporary boards in set-core, removed afterwards. Fleet: chip `19 · 33 · 8 · ⛓1` with aria `1 dangling dependency`; rows `blocks 1` and `waits on 2` (amber, one reference dangling); the list floats. Page: Waves shows `waiting` chips with `waits on vc-build/cli · todo` and `waits on nowhere/x · no board 'nowhere' there`; Kanban puts both in blocked; the prerequisite board shows `blocks 1` with the tooltip naming `vc-rollout/migrate (todo)`
- [x] 5.4 Live: `share` over this machine's boards prints the step with the editor list (values not copied anywhere) — `share --repo <consumer>`: 2 boards, SHARE line with 3 editors, session is the owner account; the consumer tree unchanged (`git status` empty). The CLI cannot see who OWNS an existing artifact, only which account the session is

## 6. Round 2 — the combined board (2026-11-08)

- [x] 6.1 Team scope: `projects` in the editor list, fnmatch over registry names; nothing outside it reaches the combined board; no scope = nothing pushed [REQ: the-combined-board-is-scoped-to-the-team-s-projects] — the owner narrowed it mid-round: the AI+ development, not every project on the machine
- [x] 6.2 `sync` writes the combined document, `PUSH-COMBINED`, `pending`, `pushed --combined`; the hook carries both pushes in one block [REQ: every-board-in-scope-is-one-document-on-the-combined-board]
- [x] 6.3 `templates/waveboard/combined.html`, `combined-page`, `combined-link`; `overview` follows the scope, `--all` widens it [REQ: the-combined-page-lists-every-board-and-the-edges-between-them]
- [x] 6.4 Tests: 9 new in `tests/unit/test_wave_board.py` (71 passed); mutations caught: scope ignored in sync (1 fail), scope ignored in the seed (1), an empty scope matching all (1)
- [x] 6.5 Visual check of the rendered page in Chrome (local server): a 266-item board's per-item strip overflowed its row, so the strip became one proportional segment per status, and the strips now share one left edge (measured: one x for all 13). An opened row lists the open items. The published page could NOT be looked at live at first: the browser is signed in as an account it was not shared with yet ("Page not found"). After the owner shared it (2026-11-08), the same browser shows it LIVE: 13 boards, 345 of 603 items done, and rows refreshed by the projects' own pushes (4 and 14 minutes old, the seed was 32)
- [x] 6.6 Live: published the combined Artifact from the owner account (session = owner, measured); `combined-link` recorded it (list stays 0600); the scope was set from the umbrella's own `docs/projects.json` relations (self, base, product, product-support, public-channel; white-label twin and tooling left out), 12 of its 22 names are registered here; 13 boards written as `boards/<project>--<job>`. One document was already there, pushed by a consumer agent's own Stop hook minutes after `combined-link`, so the chain ran end to end without help

- [x] AC-15 Outside the scope or without a scope, nothing reaches the combined board [REQ: the-combined-board-is-scoped-to-the-team-s-projects]
- [x] AC-16 Combined push cycle and one hook block for both pushes [REQ: every-board-in-scope-is-one-document-on-the-combined-board]
- [x] AC-17 The seed holds the in-scope boards with their edges, not the out-of-scope one [REQ: the-combined-page-lists-every-board-and-the-edges-between-them]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1 `link` prints the URL, every editor with edit access, and the owner [REQ: the-share-step-names-the-editors-and-the-owner-account]
- [x] AC-2 A session account different from the owner is called out [REQ: the-share-step-names-the-editors-and-the-owner-account]
- [x] AC-3 No editor list: `link` succeeds and says where the list belongs [REQ: the-share-step-names-the-editors-and-the-owner-account]
- [x] AC-4 No address from the list lands in the job file or payload [REQ: the-share-step-names-the-editors-and-the-owner-account]
- [x] AC-5 The hook's reason names the owner and edit access, without `SET_WAVEBOARD_PUSH=off` [REQ: a-refused-push-asks-for-edit-access]
- [x] AC-6 `depend j a other:k/b` stores the reference; a malformed one exits 2, file unchanged [REQ: an-item-can-depend-on-another-board-s-item]
- [x] AC-7 done = met; skipped = unmet with status; unregistered = unmet with reason [REQ: a-dependency-is-met-only-by-a-done-item-and-never-by-an-unknown-one]
- [x] AC-8 The prerequisite finishing changes the dependent's hash and makes it pending [REQ: the-payload-carries-what-each-item-waits-on-and-what-it-blocks]
- [x] AC-9 `waiting_on` on the dependent and `blocks` on the prerequisite [REQ: the-payload-carries-what-each-item-waits-on-and-what-it-blocks]
- [x] AC-10 `set … done` on a waiting item exits 2, file unchanged; `--force` sets it [REQ: a-waiting-item-cannot-be-started-by-report]
- [x] AC-11 Waiting todo drawn as blocked in both views; old payload unchanged [REQ: the-page-shows-waits-on-and-blocks]
- [x] AC-12 `overview --json` lists both boards and the unmet edge [REQ: overview-is-the-combined-view-over-every-registered-project]
- [x] AC-13 The fleet entry carries `deps_out`/`deps_in`/`waiting`; a dangling reference counts in `deps_unresolved` with null status [REQ: the-summary-carries-the-dependency-edges-between-boards]
- [x] AC-14 Row shows "waits on N" / "blocks N"; the closed chip shows the dangling count [REQ: the-rows-and-the-chip-show-the-dependencies]
