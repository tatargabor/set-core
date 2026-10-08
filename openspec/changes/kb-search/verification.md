# kb-search — verification notes (W4)

Numbers carry no project names (task 6.3). Every line says the command that produced it.

## 6.1 — unit suite and `set-kb doctor`

| OS | Python | SQLite | unit suite | doctor on the fixture |
|---|---|---|---|---|
| Linux 6.8 (x86_64), 2026-10-08 | 3.14.3 (venv and system) | 3.51.2 | `pytest -q tests/unit -k kb` → **236 passed** | exit 0; index present, 18 files / 37 chunks, the three exclusion rules counted |
| macOS | — | — | **open** — no macOS machine reachable from this session | — |

## 6.2 — the fixture at two absolute paths

Linux, 2026-10-08: the fixture staged as in `test_kb_fixture_commands.fixture_project` at
`<tmp>/a/fixtureproj` and `<tmp>/b mély/ékezetes út/fixtureproj` (space + accents in the
clone location); all 15 `queries.json` queries run with `set-kb search --json`.

- **15/15 pages identical** once the envelope's `root` field is set aside — `root` is the
  absolute project root the query ran in, by design; it is neither a hit path nor stored.
  Hit paths, order and every other field match.
- **No index file holds the clone location** (byte search, UTF-8 and UTF-16LE, over `.set/`).
- **AC-4, Linux side:** the accented hit is stored and returned as NFC
  (`corpus/planning/költségvetés-jegyzet.md`).
- **Open:** the two macOS clones and the cross-OS comparison (four pages per query).

Note for the cross-OS run: compare pages **without** `root`, or the comparison fails on
the one field that is meant to differ.

## 6.3 — build and refresh time on the largest registered corpus

Linux, 2026-10-08, on a `git clone --local` of the largest registered project (the live
tree untouched): 5,732 files scanned, 51,004 chunks.

| measurement | result | target |
|---|---|---|
| full build (`set-kb index --full`) | **192.6 s**, peak RSS 64 MB | — |
| no-change refresh (`set-kb index`), 3 runs | **0.57 / 0.81 / 0.57 s** | < 1 s on ~4k files ✓ |
| search including its refresh | 0.72 s | — |

The full build is the one-time cost on a fresh clone or after `--full`; at 3 minutes it is
worth naming in the rollout notes (W5) so a first `set-kb search` in a big project is not
mistaken for a hang.

## 7.1 — re-deploy on this machine (2026-10-08)

`set-project init` at `81f96c5d` in every registered project and each of its worktrees:
**50 trees, init exit 0 in all 50**, one commit per tree carrying only the files the deploy
wrote (pathspec; the set:kb skill and the `set-kb-search` rule in every tree, the wave-board
Stop hook in 18 worktrees the 2026-10-07 rollout had missed). Skipped: two registrations that
are not git repositories, one throwaway `/tmp` worktree. In 7 trees the deploy also wrote into
a file that already carried another session's uncommitted edit (`.gitignore`,
`.claude/settings.json`, `.claude/.set-version`, `CLAUDE.md`, an orchestration config) —
left uncommitted, to travel with that work. `install.sh` had no `set-kb` in its link list,
so the deployed skill and rule would have hit "command not found" (`81f96c5d`).

## 7.2 — doctor and findability in every registered project (2026-10-08)

31 registered projects on this machine (E2E run directories excluded). Per-project JSON is
kept machine-local, outside set-core (`~/.local/share/set-core/kb-rollout/2026-10-08/`).

- `set-kb doctor`: **exit 0 in 31/31**, no blocking finding.
- `set-kb findability`: **exit 0 in 31/31**, level-1 misses 0 everywhere; the four projects
  that hold saved recordings find every one by its own title (level 2 = 1.0).
- **One anomaly, not reproduced:** in the largest project the first `set-kb index` died
  after 26 s with `sqlite3.DatabaseError: database disk image is malformed` (in `add_edge`,
  writing the `.tmp-<pid>` build file). The failure-atomic path held — no file appeared at
  the real index path, `doctor` reported "not built yet", and the next command built the
  index cleanly. Two repeat first builds over the same live tree (index in a scratch path)
  both succeeded (5,792 files, 51,309 chunks, 143–155 s). At the time another session was
  clearing disk caches on that machine; deleting a live build's WAL produces exactly this
  error, but that is a candidate, not a finding. If it recurs, the place to look is who
  touches `.set/kb/*.tmp-*` while a build runs.

## 7.3 / 7.4 — per-project configuration and client scope

- Only one project keeps client material — recordings included — in per-client folders.
  It got its own `set/knowledge/kb.json` in its own repository: a `client` scope over the
  client folders, `meetings` and `client` channels, language `hu`, **no lane** (the quota
  needs an eval sweep first). findability after the change: 134/134 indexed, 47/47 by
  title.
- **Isolation measured:** every client × 3 queries with `--scope client=<c>` — 534 hits,
  **0** outside that client's folder.
- Every other project's markdown corpus has no per-client folders (the remaining matches for
  client-ish folder names were a test fixture, YAML and JSON captures); defaults are enough.
  The project with its own engine moves its configuration in W6 (8.3), after the gate.
