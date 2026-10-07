## IN SCOPE
- The `set-kb` command line and its text and JSON output contract
- The `kb_search` and `kb_get` tools on the set-core MCP server
- The deployed `set:kb` skill and the short deployed search rule
- Delivering all of the above to every registered project through deploy
- The per-project configuration file, its layering and its validation

## OUT OF SCOPE
- Hooks that inject search results into prompts or intercept `grep`
- Reaching another project's index from inside a project
- Project-specific skills that a project writes on top of the shared one

## ADDED Requirements

### Requirement: One command line is the single implementation surface

set-core SHALL provide a `set-kb` command with the subcommands `index`, `search`, `get`,
`sources`, `eval`, `findability` and `doctor`. Every other surface SHALL call this command
rather than reimplement search. Every reading subcommand SHALL accept `--json`. The command
SHALL resolve the project from the current directory's repository root.

#### Scenario: Searching from any folder in the project
- **WHEN** `set-kb search "<query>"` runs in a subdirectory of a project
- **THEN** it searches that project's index and prints paths relative to the repository root

#### Scenario: Outside a repository
- **WHEN** `set-kb search` runs in a directory that is not inside a git repository
- **THEN** it exits non-zero with a message saying no project was found

### Requirement: The result page states what it did not search

Every search result page SHALL end with: how many matching sources exist beyond the limit, the
exclusions in force, whether the index was refreshed, and the root paths are relative to. A
page with no hits SHALL print the query it ran, so the absence can be quoted as evidence.

#### Scenario: Zero hits
- **WHEN** a search returns no hits
- **THEN** the page prints a no-hit line containing the exact query, followed by the active exclusions

#### Scenario: Results beyond the limit
- **WHEN** 40 sources match and the limit is 8
- **THEN** the page shows 8 and states that 32 more match

### Requirement: The JSON output is a stable contract

`search --json` SHALL return, per hit: repository-relative path, heading path, leaf heading,
snippet, score, channel, scope, count of further matching sections, duplicate count, and source
root; plus the footer facts as fields. Field names SHALL NOT change without a new contract
version field.

#### Scenario: A script consumes the hits
- **WHEN** a script runs `set-kb search "<q>" --json` and reads `hits[0].path`
- **THEN** it receives a repository-relative path that `set-kb get` accepts unchanged

### Requirement: A section can be fetched verbatim

`set-kb get <path>` SHALL print the file, and with a section argument SHALL print exactly that
section. A leaf heading SHALL resolve when it is unambiguous; an ambiguous leaf SHALL list its
full heading paths instead of choosing one.

#### Scenario: Ambiguous leaf heading
- **WHEN** a file has two sections whose leaf heading is "Decision" and `get` is asked for "Decision"
- **THEN** it lists both full heading paths and prints neither section

### Requirement: The MCP server exposes search to every initialized project

The set-core MCP server SHALL offer `kb_search` (query, limit, and optional root, channel,
scope and excluded path) and `kb_get` (path and optional section). Both SHALL run `set-kb` with
`--json` in the project directory the server was registered for, and SHALL return its error
text when the command fails rather than an empty result.

#### Scenario: Agent in a project calls the tool
- **WHEN** an agent in an initialized project calls `kb_search` with a query
- **THEN** it receives the hits from that project's own index

#### Scenario: Engine failure surfaces
- **WHEN** `set-kb` exits non-zero because FTS5 is missing
- **THEN** `kb_search` returns the error message, not an empty hit list

### Requirement: Agents are told when to search

Deploy SHALL install a `set:kb` skill describing when to search, how to read a hit (score,
path, heading, further sections, duplicates, channel, scope), how to narrow by root, channel,
scope or excluded path, and that zero hits describe the index rather than the world. Deploy
SHALL install a short rule stating that an agent searches before claiming there is no source or
precedent, before planning a change, and when a grep returns more files than it will read.
Project-specific layer descriptions SHALL come from the project configuration through
`set-kb sources`, not from the deployed files.

#### Scenario: Project-specific layers
- **WHEN** an agent runs `set-kb sources` in a project whose config describes its channels
- **THEN** it sees each root and channel with the description from the config

#### Scenario: Rule size
- **WHEN** the deployed rule is measured
- **THEN** it is no longer than 15 lines

### Requirement: Deploy delivers search to every registered project

`set-project init` and the deploy pipeline SHALL install the skill and the rule, SHALL register
the MCP tools through the existing set-core MCP server registration, and SHALL ensure `.set/` is
ignored by git in the project. Deploy SHALL NOT create or overwrite the project's search
configuration file.

#### Scenario: Re-deploy keeps the project config
- **WHEN** a project with its own search configuration is re-deployed
- **THEN** the configuration file is unchanged and the skill and rule are updated

#### Scenario: Project without ignore entry
- **WHEN** a project's ignore rules do not cover `.set/`
- **THEN** deploy adds the entry and reports it

### Requirement: Per-project configuration is project-owned, layered and validated

The engine SHALL read the project configuration from `set/knowledge/kb.json`, layered over an
optional machine-level file and the built-in defaults. Keys beginning with `_` SHALL be treated
as documentation and ignored. When the project file is absent and the legacy configuration
location of the originating engine exists, the engine SHALL read it and warn, naming the new
location. An invalid value SHALL fail loading with the offending key path.

#### Scenario: Documentation keys
- **WHEN** a config contains `"_why": "..."` next to `"exclude": [...]`
- **THEN** the exclusions apply and `_why` has no effect

#### Scenario: Legacy location
- **WHEN** a project has only the legacy configuration file
- **THEN** the engine uses it and prints one warning naming `set/knowledge/kb.json`

#### Scenario: Unknown language
- **WHEN** the config sets a language for which no pack exists
- **THEN** loading fails, naming the language key and the available packs
