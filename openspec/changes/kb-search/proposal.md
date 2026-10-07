## Why

Agents in set-core-managed projects answer "did we discuss this, who said it, what did we
decide, is there a precedent" with `grep`. Over a corpus of a few thousand markdown files that
returns hundreds of unranked paths, nobody reads them, and the agent plans as if the corpus
were silent. The planning documents then cite code and almost never the recorded meetings,
e-mails and notes that hold the requirements.

One consumer project already fixed this locally: it carries a ported, MIT-licensed SQLite
FTS5 engine (section-level BM25F over its own markdown, with a reserved lane for the client's
channels), a CLI, a skill, and a deterministic retrieval eval with a control arm. Its own
measurement on a mined question set: the ranked search put the right source in the top 10 for
a majority of the questions, while a fixed grep-style control did so for under one in ten. The
engine is project-agnostic by construction (every project-specific value lives in a config
file), but it lives in that one repository, so every other project still greps.

Two defects the local copy also carries make the case for a shared, tested engine rather than
a second copy:

- **A saved meeting recording is not findable.** The default exclusion of agent-log trees is
  a directory glob that also removes the human-readable transcripts saved next to the raw
  recording. Measured in the originating project: a search for the title words of a saved
  recording returns other documents, and the footer lists the excluding pattern. Recordings
  are exactly what the user needs found.
- **Setting `exclude` replaces the defaults wholesale.** A project that adds one pattern
  silently re-admits every agent-log tree the defaults kept out. The originating config
  documents this hazard by repeating the defaults by hand.

## What Changes

- **A shared knowledge-base search engine in set-core core** (`lib/set_kb/`), a stdlib-only
  Python port of the consumer's engine, which is itself a port of an MIT-licensed upstream
  package. The MIT copyright and permission notice travel with it verbatim, with per-file
  attribution on ported files.
- **One CLI, `set-kb`** (`index`, `search`, `get`, `eval`, `findability`, `doctor`,
  `sources`), the single external surface; everything else calls it.
- **Two MCP tools on the existing set-core MCP server** (`kb_search`, `kb_get`), so every
  project that `set-project init` registered reaches the search with no extra setup.
- **A deployed skill (`set:kb`) and a short deployed rule** telling agents when to search
  before they grep, plan, or claim "there is no source".
- **Per-project configuration** at `set/knowledge/kb.json` (project-owned, never overwritten
  by deploy) with zero-config defaults that index every readable markdown file and exclude
  generated trees, dependency trees, agent logs, raw `.jsonl` recordings, and unmodified
  framework-deployed files. Project `exclude` patterns ADD to the defaults.
- **A generic reserved lane**: named channels classified by root-scoped path rules, and a
  page share reserved for the channels a project names (the consumer's "client voice" lane,
  made generic). No channels configured means no lane.
- **A path-captured scope key** (for example one client folder) stored per chunk, with a
  `--scope` filter, so a project can search inside one client's material without results from
  another. It is also the key a later cross-repository, client-scoped search will join on.
- **A machine-local index** at `<project>/.set/kb/index.db`, never committed, refreshed
  incrementally on every search, seeded from the main checkout's index in a fresh worktree.
- **Per-project verification**: `set-kb doctor` (runtime, FTS5, ignore status, config,
  corpus), `set-kb findability` (every saved recording's readable transcript is indexed and
  retrievable by its own title), and `set-kb eval` over a project-owned golden set with a
  control arm.
- **Migration of the originating project onto the shared engine** behind a re-measure gate:
  the shared engine must match the local engine's recall and MRR on the same corpus snapshot
  before the local copy is retired.

## Capabilities

### New Capabilities

- `kb-search-engine`: the index and the ranked search — corpus selection and defaults,
  chunking and ranking, channels and the reserved lane, scope capture, index location,
  incremental refresh, concurrency, runtime requirements, and licence provenance.
- `kb-search-access`: how agents and humans reach it in every project — the `set-kb` CLI and
  its output contract, the MCP tools, the deployed skill and rule, deployment to every
  registered project, and the per-project configuration file.
- `kb-search-eval`: proving per project that it works — the doctor, the findability check for
  saved recordings and notes, the golden-set eval with a control arm, and the re-measure gate
  that guards a migration.

### Modified Capabilities

None. No existing capability's requirements change: the MCP server and deploy gain new
entries but keep their current contracts.

## Impact

- **Core (new):** `lib/set_kb/` (engine package), `bin/set-kb` (CLI),
  `lib/set_kb/LICENSE-UPSTREAM` (MIT notice), `tests/unit/test_kb_*.py` plus a fixture corpus.
- **Core (extended):** `mcp-server/set_mcp_server.py` (two tools that call the CLI),
  `lib/project/deploy.sh` (skill + rule deployment, `.set/` ignore check),
  `templates/core/rules/` (one short rule), `.claude/skills/set/kb/SKILL.md`,
  `README.md` third-party notices.
- **Modules:** none. The engine is corpus-agnostic and applies to every project type,
  including documentation-only projects that have no module.
- **Runtime:** Python ≥ 3.10 with an `sqlite3` module that has FTS5 — already what set-core
  requires. No Node, no native extension, no new pip dependency.
- **Consumer projects:** a fresh project works with defaults; projects with special corpora
  add `set/knowledge/kb.json`. The originating project migrates in its own repository, gated
  by the re-measure.
