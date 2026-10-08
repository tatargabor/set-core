# kb-search fixture corpus and oracle

Synthetic corpus for the shared knowledge-base search engine
(`lib/set_kb/`). It contains **no project content** — every file was written
for this fixture. The change is `openspec/changes/kb-search/`; the oracle
contract is task 1.2/1.3 there and requirement
`the-shared-engine-matches-the-reference-engine-on-a-synthetic-corpus`.

## Layout

| path | what it is |
|---|---|
| `corpus/` | the indexed corpus — four roots under `corpus/` (planning 30, meetings 20, clients 10, archive 0) |
| `kb.config.json` | one configuration that drives **both** engines identically: sources, priorities, channel rules, ranking, exclusions, `language: "hu"` |
| `queries.json` | the fixture queries; each entry is `{id, q, args}` where `args` are the search flags the page was recorded with |
| `expected/` | the recorded result pages of the reference engine — the oracle |
| `record_expected.py` | re-records `expected/` from the reference engine (see below) |

## What the corpus exercises

- **Several roots** with distinct priorities (`corpus/{planning,meetings,clients,archive}`).
- **Identical content at two priorities** — `duplicate-note.md` in `planning/` and
  `meetings/`; the higher-priority root must win and the hit must be marked as
  having a duplicate (`akaPaths`).
- **One file matching in many sections** — `planning/overview.md` (its budget
  sections must collapse to one slot reporting the rest).
- **Accent-carrying file name and content** — `planning/költségvetés-jegyzet.md`;
  the query `szamlazas dijbekero` is unaccented (FTS5 `unicode61` folding).
- **A saved recording pair** — `meetings/2026-09-12-tervezes-part1.{md,jsonl}`;
  only the readable `.md` is ever indexed (`.md`-only extension default).
- **A readable transcript whose name contains `-raw-`** —
  `meetings/2026-09-19-megbeszeles-raw-part1.md` — indexed like any other note.
- **An agent-session dump** with frontmatter `type: claude-session`
  (`meetings/sessions/`) — excluded here by configuration; the frontmatter rule
  itself is engine default from wave W2.
- **Build-output and virtualenv markdown** — `planning/dist/`,
  `planning/.venv/` — excluded (build trees by engine default, `.venv/` by config).
- **An archive folder** — `corpus/archive/` — indexed: the archive is the
  decision history.
- **Channel classification** — `client` (root `corpus/clients`) and `meetings`
  (root `corpus/meetings`, `meetings/**` + `minutes/**`), including the
  root-scoping case: `clients/meetings/standalone-minutes.md` shares the folder
  name but sits under another root, so it must stay unclassified.
- **The reserved lane** — `client-lane-reorder` is the page where the lane
  visibly reorders: the buried client hit takes a slot ahead of a
  higher-scoring planning document; `client-lane-off` is the same corpus with
  the quota disabled.

## Re-recording the oracle

`expected/` is produced by the **reference engine** (the TypeScript port the
shared engine was ported from). It runs in its own repository; this fixture
never names it. With that repository available:

```bash
KB_REFERENCE_CLI=/path/to/the/reference/cli.ts \
    python3 tests/fixtures/kb/record_expected.py
```

The script copies the fixture to a temp directory, indexes it, and writes one
JSON page per query. It strips the machine-local `cwd` field the reference
embeds — everything else is stored verbatim. All corpus file names are checked
to be NFC before recording (paths are stored NFC-normalised, task 2.4).

Record only when deliberately re-pinning the oracle, and update the pinned
commit in `expected/README.md` in the same commit.
