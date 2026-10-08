[< Back to Reference](README.md)

# Knowledge-base search — `set-kb`

Section-level full-text search over a project's own markdown: plans, decisions, meeting
notes, saved recordings. One engine for every project (`lib/set_kb/`, stdlib Python on
`sqlite3` + FTS5, BM25F ranking), one command line as its single implementation surface.
The `set-core` MCP server's `kb_search` / `kb_get` tools and the `set:kb` skill call the
same code.

## Commands

| Command | What it does |
|---|---|
| `set-kb search "<query>"` | Ranked sections. Refreshes the index incrementally first. |
| `set-kb get <path> [--section <heading>]` | A file, or one section of it, verbatim. |
| `set-kb index [--full]` | Build or refresh the index without searching. |
| `set-kb sources` | Roots, channels and the lane, each with the project's own `about` line. |
| `set-kb doctor` | Whether search works in this project: blocking vs informational checks, per-root, per-channel and per-exclusion-rule counts. |
| `set-kb findability` | Saved recordings and named notes must be indexed (level 1) and come back for their own title (level 2). Exits non-zero on a level-1 miss. |
| `set-kb eval` | Retrieval metrics over the project's golden set, with a control arm. |

Every command takes `--json` (a versioned, stable contract) and `--verbose` (debug log on
stderr).

Useful `search` flags: `--limit`, `--root <ref>`, `--channel <name>`,
`--scope <name>=<value>`, `--exclude-path <fragment>` (repeatable), `--no-lane`,
`--no-reindex` (measure the index as it stands), `--full`.

The JSON page's `root` field is the absolute root of the project the query ran in. It is
the only absolute path on the page: hit paths are repository-relative, `/`-separated and
NFC, and identical wherever the repository is cloned. Compare pages across machines
**without** `root`.

## The index

- **Location:** `<project>/.set/kb/index.db` with its WAL sidecars. The engine runs
  `git check-ignore` first and **refuses to build** when the path is not ignored: the WAL
  holds corpus text verbatim, which can be client correspondence. `set-project init`
  makes sure `.set/` is in `.gitignore`.
- **Refresh:** incremental on every `search` (mtime + size, then sha256; deleted files
  dropped). A changed schema version, SQLite version or corpus-affecting config forces a
  full rebuild, announced in one line.
- **Cost, measured** (Linux, 2026-10-08, ~5.7k files / 51k chunks): no-change refresh
  0.6–0.8 s; **first full build about 3 minutes**. A first search in a big project is the
  build, not a hang.
- **Worktrees:** a linked worktree without an index copies the main checkout's and refreshes
  from there.
- **Concurrency:** one writer (`.set/kb/index.lock`). A search that cannot take the lock
  answers from the current snapshot and says so.

## Configuration — `set/knowledge/kb.json`

Project-owned: `set/knowledge/` is never touched by a framework deploy. Three layers merge
in order — built-in defaults ← `~/.config/set-core/kb.json` (machine, optional) ← the
project file. Nested objects merge field by field; arrays replace, **except `exclude`,
which adds at every layer**. Keys starting with `_` are documentation and are dropped on
load. Validation is loud: an invalid config fails with the offending key path and never
falls back to defaults.

A project still carrying the legacy `kb.config.json` at its root is read from there, with a
one-line warning naming the new path.

| Key | Default | Meaning |
|---|---|---|
| `language` | `"en"` | Language pack (stopwords, query tokenizer). `"hu"` ships. Accent folding is FTS5 `unicode61` either way. |
| `sources` | `[{"ref": ""}]` (the whole repository) | Indexed roots: `{ref, priority?, about?}`. Priority decides which copy wins when identical content sits in two roots; the loser is reported as `akaPaths`. |
| `extensions` | `[".md"]` | File types indexed. |
| `exclude` | `[]` | The project's own glob patterns — **added** to the defaults below. |
| `excludeDefaults` | `true` | `false` lifts every default exclusion group. |
| `keepDefault` | `[]` | Lifts exactly the named default groups. An unknown name is an error. |
| `excludeFrontmatter` | `{"type": ["*-session-claude-code", "claude-session"]}` | Frontmatter values that keep a file out wherever it is saved — agent-session dumps, while the readable transcript beside them stays in. |
| `includeFrameworkFiles` | `false` | Files set-core deployed and the project never edited (per `set/.deploy-manifest.json`) are not project knowledge. A file the project edited is indexed. |
| `channels` | `[]` | Ordered rules `{channel, roots[], include?[], exclude?[], about?}`; first match wins. `roots` is mandatory, so a path *about* a client is not mistaken for the client's own voice. |
| `scopes` | `[]` | `{name, pattern}` with `{scope}` exactly once, e.g. `docs/clients/{scope}/**`. The captured value is stored per chunk; `--scope client=<value>` restricts a page to it. |
| `ranking.fieldWeights` | `headingPath 10 · heading 3 · body 1` | BM25F field weights. |
| `ranking.laneChannels` / `laneQuota` / `laneLeadMargin` | `[]` / `0` / `0` | The reserved lane: a share of the page kept for hits from the named channels. Empty `laneChannels` means **no lane**. The quota is a per-project measurement (an eval sweep), never a copied default. |
| `ranking.sourceDedup` | `true` | Collapse identical content across roots. |
| `ranking.proximityBoost`, `ranking.diversity`, `ranking.coverageRerank` | off | Optional re-ranking stages. |
| `findability.globs` | `[]` | Extra "named notes" that `findability` must be able to find. |

### Default exclusion groups

`.git/` and `.set/` are always pruned and cannot be lifted. Everything else is a named group
that `keepDefault` can lift:

| Group | Patterns |
|---|---|
| `dependencies` | `node_modules/` |
| `worktrees` | `**/worktrees/` |
| `build-output` | `dist/`, `build/`, `out/`, `coverage/`, `.next*/`, `.nuxt/`, `.turbo/`, `.cache/`, `test-results/`, `playwright-report/` |
| `virtualenvs-and-caches` | `.venv*/`, `venv/`, `.pytest_cache/`, `.mypy_cache/`, `__pycache__/` |
| `vendored-trees` | `vendor/`, `3rdparty/`, `third_party/` |
| `agent-logs` | `**/claude-sessions/`, `**/tool-calls/` |

**Why these:** they are either regenerated (build output, caches), someone else's knowledge
(dependencies, vendored code), or a machine's log of its own work (agent logs). Searched,
they bury the project's decisions under text nobody on the project wrote. Saved
**recordings** are deliberately *in*: their readable `.md` transcript is project knowledge.

### Example

```json
{
  "_why": "client folders are isolated; meetings get a reserved share of the page",
  "language": "hu",
  "sources": [
    { "ref": "docs", "priority": 2, "about": "plans and decisions" },
    { "ref": "docs/inputs", "priority": 1, "about": "saved dictations and meetings" }
  ],
  "exclude": ["docs/archive/drafts/**"],
  "channels": [
    { "channel": "meetings", "roots": ["docs/inputs"], "about": "what was said, verbatim" }
  ],
  "scopes": [{ "name": "client", "pattern": "docs/clients/{scope}/**" }],
  "ranking": { "laneChannels": ["meetings"], "laneQuota": 0.2 }
}
```

`laneQuota: 0.2` here stands for a value the project measured with `set-kb eval`; do not
copy it.

## Verification

Run these after deploying to a project, and again after changing its config:

```bash
set-kb doctor          # blocking problems exit non-zero; counts per root, channel, rule
set-kb findability     # recordings + named notes indexed and retrievable by title
set-kb eval            # golden set: set/knowledge/kb-golden.json (project-owned)
```

The golden set is `{"queries": [{"id", "q", "targets": [...]}]}` — several targets per
query are allowed. `eval` always runs a control arm and treats an unanswerable query as a
miss (the denominator is fail-closed). Use `--no-lane` to measure the lane's effect, `--k`
to change the depth. Keep per-project results in the project, never in set-core.

## Moving a project off its own engine

A project with a local copy of the originating engine switches only after a re-measurement
on a frozen corpus: hits not lower and MRR within 0.005, with the lane off and on. Then the
callers point at `set-kb`, the config moves to `set/knowledge/kb.json`, the new default
corpus is measured once more (recorded as a corpus change), and only then the local engine
is removed. See `openspec/changes/kb-search/` (W6).

## Provenance

The engine is a Python port of an MIT-licensed upstream, through an intermediate TypeScript
port. The full licence, the upstream commit and the list of divergences are in
`lib/set_kb/LICENSE-UPSTREAM`.
