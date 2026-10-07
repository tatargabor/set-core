## Context

A consumer project carries a working knowledge-base search: a TypeScript port of an
MIT-licensed upstream package (SQLite FTS5, BM25F over markdown sections, with dedup,
diversity and a reserved lane), run on Node's built-in `node:sqlite` with type stripping, so
it needs no `node_modules`. Its surfaces are a CLI and a project skill; there is no MCP tool
and no hook. The index is a gitignored SQLite file inside the repository, refreshed
incrementally on every search (layered mtime+size, then sha256) and rebuilt atomically
(temp file + rename) on the first run. The retrieval eval is deterministic, reads a
`{id, q, targets[]}` golden set, runs a control arm, and never shrinks the denominator on a
failed search.

What the local copy got right is the reason to lift it as it is, not to redesign it:
project-agnostic engine, all vocabulary in a config file, root-scoped channel rules, the
archive indexed as decision history, agent-log trees excluded by default, and a page footer
that states which exclusions were in force. What it got wrong is listed in the proposal:
a directory-level exclusion that hides saved recordings, and an `exclude` array that
replaces the defaults.

set-core's own constraints shape the port:

- set-core is a Python + bash framework. `install.sh` requires Python ≥ 3.10 and installs
  `uv` for the MCP server; Node is installed through Homebrew on macOS but is **not** a
  prerequisite on Linux.
- The set-core MCP server (`mcp-server/set_mcp_server.py`, fastmcp under `uv`) is already
  registered per project by `lib/project/deploy.sh` with `CLAUDE_PROJECT_DIR` set, so a tool
  added there reaches every initialized project.
- Modules (`modules/web`, `modules/mobile`) are `ProjectType` profiles — they specialise
  build, test and verification for a kind of application. A documentation-only project has
  no module at all.
- set-core persists nothing derived from consumer data (CLAUDE.md, External Project
  Confidentiality). Golden sets, measured baselines and consumer configs stay in the
  consumer's repository.
- Every registered project carries roughly 60–90 markdown files that set-core deployed into
  `.claude/` (rules, skills, commands). Indexed, they are identical across projects and win
  generic queries with framework boilerplate.

A rough census of the registered projects on the authoring machine (excluding E2E run
directories): markdown corpora range from a handful of files to several thousand; the large
ones are dominated by `openspec/changes/`, `docs/inputs`-style raw material, knowledge
folders and client folders; several projects carry build or virtualenv trees that contain
markdown (`.next*/standalone`, `.venv*/lib`, vendored `3rdparty/`), one of them several
thousand files. Saved recordings exist as `.jsonl` next to a readable `.md` in at least three
layouts: a dated inputs tree, per-client `meeting-notes/`, and per-topic `transcript/`
folders, and the readable file's name sometimes contains `raw`.

## Goals / Non-Goals

**Goals:**

- One engine, in set-core, used by every registered project through the same CLI, MCP tool
  and skill, on macOS and Linux, across machines where the repositories sit at different
  paths.
- Zero-config usefulness: a project with no config gets a sane corpus.
- Findability as the acceptance test: a saved recording's readable transcript, or any note,
  is indexed and retrievable — checked per project by a deterministic command.
- Migrate the originating project without regressing its measured recall and MRR.
- Carry the MIT notice.
- Leave a clean seam for a later cross-repository, client-scoped search.

**Non-Goals:**

- Cross-repository (federated) search, and client-scoped two-way search across repos. This
  change only stores the scope key and keeps indexes addressable by registry name.
- Semantic / embedding search, reranking models, query expansion by an LLM. The upstream's
  model-dependent flags were already dropped by the local port; they stay dropped.
- Usage self-measurement (call log, "did the returned source end up cited") and chronology
  on the result page (per-hit dates, `--since`). The originating project has an open change
  for both; they become a set-core follow-up once the engine is shared (see Open Questions).
- A guard hook that intercepts `grep` over the docs and redirects to the search.
- The downstream-effect harness (an LLM answering with and without search hits). It is
  project-specific and stays in the consumer.
- Windows.

## Decisions

### D1 — Core package, not a module or an external plugin

The engine goes to `lib/set_kb/` with the CLI at `bin/set-kb`.

- **Rejected: a `modules/*` project-type module.** Modules specialise an application type
  through the `ProjectType` ABC. Search is corpus-agnostic and needed by projects that have no
  module (documentation, sales, research repositories); hanging it on a profile would leave
  exactly those projects without it.
- **Rejected: an external plugin repository.** A second install path and version skew,
  for a capability the user wants in every project. The deploy pipeline that reaches every
  project is set-core's.
- **Rejected: keep per-project copies.** The local copy took a dozen fix commits after its
  change was archived; each further copy would have to receive every one of them.

Project specifics (roots, channels, lane, scopes, language) stay in the project's config
file, which keeps the core abstract as `set-code-quality` requires.

### D2 — Runtime: a stdlib-only Python port on `sqlite3` + FTS5

- **Chosen:** Python ≥ 3.10, standard library only (`sqlite3`, `hashlib`, `fcntl`,
  `json`, `re`, `unicodedata`). FTS5 ships enabled in the Python builds set-core meets in
  practice: `uv`-managed CPython, Homebrew, python.org installers, and Debian/Ubuntu
  packages. `set-kb doctor` probes `CREATE VIRTUAL TABLE … USING fts5` and the `porter
  unicode61` tokenizer at startup and fails loudly with the remediation
  (`uv python install`) instead of degrading.
- **Rejected: lift the TypeScript engine as it is and run it on `node:sqlite`.** Node is not
  a set-core prerequisite on Linux. Type stripping needs Node ≥ 22.18 / 23.6 (not the 22.13
  `node:sqlite` threshold), `node:sqlite` is experimental and prints a warning on every
  run before user code executes, and it would make a Python framework depend on a second
  runtime for one feature.
- **Rejected: `better-sqlite3` or any npm native module.** A per-platform, per-arch native
  build in every project's `node_modules`.
- **Rejected: a different search library (tantivy, whoosh, ripgrep + scoring).** Different
  ranking — the measured behaviour would not carry over, and the measurement is the reason
  for the work.

**The port risk is real and is handled with an oracle, not with care.** The reference engine
exists and runs. Wave 0 runs it over a synthetic fixture corpus committed to set-core and
records its result pages; the Python engine must reproduce them (same sources, same order on
the fixture queries). The consumer-side re-measure gate (D12) then checks the real corpus.

**SQLite variance.** Python's `sqlite3` links the platform's SQLite, so versions differ
between machines. `bm25()` and the `porter unicode61` tokenizer are stable across the
versions in use; the index records `sqlite_version` and the engine's schema version in
`kb_meta`, and a mismatch forces a rebuild — the index is per machine anyway (D5).

**Path identity across machines.** Paths are stored repository-relative, POSIX-separated, and
NFC-normalised before indexing, so an accented file name walked on macOS and on Linux yields
the same key and the same searchable path text.

### D3 — Surfaces: CLI as the single surface; MCP tool, skill and rule on top

- `set-kb` is the only implementation surface: `index`, `search`, `get`, `sources`,
  `eval`, `findability`, `doctor`. `--json` on every reading command.
- **MCP:** `kb_search(query, limit, root?, channel?, scope?, exclude_path?)` and
  `kb_get(path, section?)` on the existing set-core MCP server. They run `set-kb … --json`
  as a subprocess with `cwd = CLAUDE_PROJECT_DIR`. One code path; the MCP server's `uv`
  environment needs nothing new; an engine bug is fixed once.
- **Skill:** `set:kb`, deployed with the other set skills — when to search, how to read a
  hit, and that zero hits is a statement about the index, not about the world. Project-
  specific layer descriptions come from the config (`channels[].about`), printed by
  `set-kb sources`, so the deployed skill stays generic.
- **Rule:** a short rule (`templates/core/rules/kb-search.md`, deployed as `.claude/rules/set-kb-search.md`, at most 15 lines, loaded every turn):
  search before claiming there is no precedent, before planning a change, and when a grep
  returns more files than you will read.
- **Rejected: skill only.** The originating project measured heavy under-use while the
  search was a skill an agent had to think of; the MCP tool appears in every session's tool
  list, and the rule names the moments to use it.
- **Rejected: a hook that injects search results into every prompt.** Context cost in every
  session of every project, for results nobody asked for. Revisit only with usage data.

### D4 — Configuration: `set/knowledge/kb.json`, additive excludes

- **Location:** `set/knowledge/kb.json` in the project. `set/knowledge/` is project-owned
  and never touched by `set-project init`. JSON, because the engine is stdlib-only; keys
  starting with `_` are documentation and are dropped on load (the originating config uses
  this to keep every decision next to its value).
- **Layering:** built-in defaults ← optional machine file `~/.config/set-core/kb.json` ←
  project file. Nested objects merge; arrays follow the exclude rule below.
- **Legacy path:** if the project file is absent and the originating engine's legacy
  config path exists, the loader reads it and warns once per run, naming the new path.
  This makes the migration a two-step change rather than a flag day.
- **`exclude` ADDS to the default exclusions.** Opting out of a default requires the
  explicit `"excludeDefaults": false` (or naming the default to drop in
  `"keepDefault": [...]`). This removes the hazard where one added pattern silently
  re-admitted every agent-log tree.
- **Validation is loud:** an unknown language, a channel rule without roots, a scope pattern
  without `{scope}`, or a non-string pattern is a config error with the key path, never a
  silent fallback.

### D5 — Default corpus

With no config the corpus is every `**/*.md` under the repository root, and:

- **Extensions: `.md` only.** A raw `.jsonl` recording is never indexed: it is line
  fragments with speaker labels and timestamps, the readable `.md` saved next to it is the
  form a human and an agent read, and indexing both would put every recording on the page
  twice. This replaces the directory-level exclusion that hid recordings.
- **Excluded trees:** `.git/`, `.set/`, `node_modules/`, `**/worktrees/**`, build output
  (`dist/`, `build/`, `out/`, `coverage/`, `.next*/`, `.nuxt/`, `.turbo/`, `.cache/`,
  `test-results/`, `playwright-report/`), virtualenvs and tool caches (`.venv*/`, `venv/`,
  `.pytest_cache/`, `.mypy_cache/`, `__pycache__/`), vendored trees (`vendor/`,
  `3rdparty/`, `third_party/`), and agent-log trees (`**/claude-sessions/**`,
  `**/tool-calls/**`).
- **Agent-session dumps by frontmatter, not by folder:** `excludeFrontmatter` (default
  `{"type": ["*-session-claude-code", "claude-session"]}`) drops a file whose frontmatter
  says it is a dump of an agent session, wherever it is saved. The readable transcript in the
  same folder stays in.
- **Unmodified framework-deployed files** (present in `set/.deploy-manifest.json` with an
  unchanged hash) are excluded; a project that edited one owns it, and it is indexed. Opt in
  with `"includeFrameworkFiles": true`.
- **Not excluded:** `openspec/changes/archive/` and any other archive — it is the decision
  history.
- The page footer always lists the exclusions in force, as the local engine does.

### D6 — Index location, refresh, worktrees

- **Location:** `<project>/.set/kb/index.db` (and its `-wal`/`-shm` sidecars). `.set/` is
  the runtime directory already ignored in initialized projects. Before writing, the engine
  runs `git check-ignore` on the index path and **refuses to build** if it is not ignored:
  the WAL file carries corpus text verbatim, which in client folders is client
  correspondence. Deploy ensures `.set/` is in `.gitignore`.
- **Rejected: an XDG cache keyed by absolute path.** The path differs per machine and per
  worktree, entries orphan when a worktree is removed, and a later cross-repo search would
  have to reconstruct the key; `<registry path>/.set/kb/index.db` is addressable by the
  project's registry name alone.
- **Rejected: committing the index.** Over a hundred megabytes on the largest corpus,
  binary churn on every note, and client text in a committed artifact.
- **Refresh:** incremental on every `search` (layered mtime+size, then sha256; deleted files
  removed), `index --full` on demand, atomic first build (temp + rename). A changed schema
  version, SQLite version, or corpus-affecting config hash forces a full rebuild with a
  one-line notice. `--no-reindex` for measurement runs.
- **No hook.** A SessionStart warm-up would cost every session of every project for a tool
  not every session uses; the incremental refresh is cheap on a warm index.
- **Worktrees:** when the index is absent in a linked worktree and present in the main
  checkout (`git worktree list --porcelain`, first entry), the engine copies it and then
  refreshes incrementally, instead of a full build.

### D7 — Concurrency

One writer per index through an advisory lock on `.set/kb/index.lock` (`fcntl.flock`,
available on macOS and Linux). A `search` that cannot take the lock immediately searches the
current snapshot without refreshing and says so in the footer. WAL mode lets readers proceed
during a refresh; a `busy_timeout` covers the commit window.

### D8 — Channels and the reserved lane, generic

- `channels`: ordered, root-scoped rules `{channel, roots[], include?[], about?}`; first match
  wins; a rule without roots is rejected (a bare path pattern misclassified a ticket *about*
  a client report as the client's voice in the originating project).
- `ranking.laneChannels`, `ranking.laneQuota`, `ranking.laneLeadMargin` keep the local
  engine's semantics: a share of the page is reserved for hits from the named channels.
- **Divergence from upstream:** an empty `laneChannels` means **no reserved lane**. Upstream
  silently falls back to a lane for agent-instruction files, which on a project corpus
  reserves the page for `CLAUDE.md`-type files.
- The quota value is a per-project measurement (its eval sweep), never a copied default.

### D9 — Scope capture

`scopes: [{"name": "client", "pattern": "docs/clients/{scope}/**"}]` captures a scope value
from the path at index time and stores it per chunk. `--scope client=<value>` restricts the
page to that value; every hit shows its scope. Within one repository this lets a project
whose client folders must stay isolated search one client's material without another's
appearing. It is also the join key a later federated, client-scoped search across
repositories will use; that search is out of scope here.

### D10 — Language packs

`language` selects a pack (stopwords, query-tokenizer specifics): `en` default, `hu`
shipped. Accent folding is FTS5's `unicode61` (`remove_diacritics`), not ours — the local
measurement found no gain from a stemmer for the agglutinative case. An unknown language is
a config error.

### D11 — Licence and provenance

`lib/set_kb/LICENSE-UPSTREAM` reproduces the upstream MIT licence **in full** (copyright line
and permission notice — the licence requires both to travel with copies or substantial
portions), the upstream repository URL and commit SHA, and a lineage note: ported to Python
from an intermediate TypeScript port whose divergences (query tokenizer, stopwords, lane
semantics, excluded trees, chunk parent link, dropped trust machinery) are carried. Each
ported module's first line is a fixed attribution line pointing at that file; new modules do
not carry it. A Python translation of the logic is a derivative work, so the notice is
carried even though no line of the original source text survives. `README.md` gains a
third-party notices entry.

### D12 — Verification per project, and the migration gate

- **`set-kb doctor`:** Python version, FTS5 + tokenizer probe, SQLite version, config
  validity, index ignored by git, corpus counts by root and channel, excluded-file counts by
  rule, index freshness. Non-zero exit on any blocking finding.
- **`set-kb findability`:** discovers saved recordings — a readable `.md` whose directory
  holds a `.jsonl` with the same stem or the same date-and-part prefix — plus any
  `findability.globs` the project adds (notes it wants guaranteed). Level 1: each must be
  indexed; a miss names the rule that excluded it. Level 2: a query built from the file's
  title or first heading (stopwords removed, no tokens from the path) must return it in the
  top k (default 10); the rate is reported with the misses listed. Deterministic, no AI.
- **`set-kb eval`:** the local evaluator's contract — `{id, q, targets[]}` golden set,
  multi-target pairs, control arm with the control query printed, failed searches counted as
  misses, Recall@k / MRR / rank-1 / top-3 / top-5. The golden set lives in the project
  (`set/knowledge/kb-golden.json` by default) and never in set-core.
- **Re-measure gate for the originating project:** on one frozen corpus snapshot, with the
  legacy config verbatim (its own exclusions, so the corpus is identical), run the reference
  engine and the shared engine through both arms (lane quota off and on). The shared engine
  passes when its hit count is not lower and its MRR is not lower by more than 0.005 in each
  arm, and a per-query page diff is attached. Baselines are re-run on the snapshot, never
  quoted from an earlier measurement. Only after the gate passes does the project move to the
  new defaults (recordings in), and that move is measured separately as a corpus change.

## Risks / Trade-offs

- **Port fidelity** → the fixture oracle (wave 0) and the consumer re-measure gate; the
  reference engine stays runnable in the consumer until the gate passes.
- **Python build without FTS5** → loud doctor failure with remediation; no silent fallback
  to grep.
- **First full index is slow on the largest corpora** → atomic build, progress on stderr,
  worktree seeding; target: a no-change incremental refresh under one second on ~4k files.
- **Including recordings changes rankings in projects that tuned their lane** → the corpus
  change is measured separately from the engine change (D12), and the lane quota is
  re-swept if it moves.
- **Framework-file exclusion depends on the deploy ledger** → a project without a ledger
  indexes `.claude/` like any other tree; doctor reports the count so the noise is visible.
- **Scope capture invites cross-repo expectations** → stated as a non-goal; the federated
  search gets its own change.

## Migration Plan

1. Freeze engine edits in the originating project; pin the reference commit.
2. Build and verify the shared engine against the fixture oracle (set-core only).
3. Ship CLI, MCP tools, skill, rule; deploy to every registered project; run doctor and
   findability everywhere; add `set/knowledge/kb.json` where defaults are not enough.
4. In the originating project: run the re-measure gate; on pass, point its `kb` script and
   callers at `set-kb`, move its config to `set/knowledge/kb.json`, then switch to the new
   defaults and measure that change on its own.
5. Remove the local engine copy in the originating project.

**Rollback:** until step 5 the local engine is intact; reverting the script and caller edits
restores it. In set-core the change is additive; removing the skill, rule and MCP tools
returns every project to its prior state, and the index under `.set/` can be deleted freely.

## Open Questions

- Whether the originating project's open change for chronology and usage self-measurement
  is finished locally first or re-targeted as a set-core follow-up (this design assumes
  re-targeting, with the local engine frozen meanwhile).
- Whether the upstream repository may be named in set-core's public tree — the MIT notice
  requires the copyright line regardless.

## Decisions taken by the user (2026-10-07)

1. **The originating project's open change (chronology, usage self-measurement) moves to a set-core
   follow-up**; that project's local engine is frozen (W0) and replaced through the W6 gate.
2. **Upstream credit: the MIT copyright line only.** The ported files and `LICENSE-UPSTREAM` keep the
   copyright notice the licence requires; set-core's public tree does not name the upstream repository
   or its organisation beyond that line.
3. **macOS proof (W4) runs on the Mac mini**, after a pull there.
4. **Client scoping is on by default where a project declares client folders** (working inside a
   declared client folder searches that folder plus the project's cross-client shared docs;
   `--scope all` for internal work).
