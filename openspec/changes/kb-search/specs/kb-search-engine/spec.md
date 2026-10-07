## IN SCOPE
- Building and refreshing a section-level full-text index over a project's markdown
- The default corpus, and how a project adds to or narrows it
- Ranked search with source dedup, channels, a reserved lane and a scope filter
- Where the index lives, how it stays out of git, and how concurrent callers share it
- The runtime the engine needs on macOS and Linux, and how its absence is reported
- Carrying the upstream licence notice

## OUT OF SCOPE
- Searching several repositories in one query (federated or client-scoped across repos)
- Semantic, embedding or model-based ranking and query expansion
- Per-hit dates, date filters and usage self-measurement
- Windows

## ADDED Requirements

### Requirement: The engine runs on set-core's existing runtime

The engine SHALL run on Python 3.10 or later using only the standard library, with SQLite's
FTS5 extension and the `porter unicode61` tokenizer. When FTS5 or the tokenizer is not
available the engine SHALL stop with an error that names the missing piece and a remediation,
and SHALL NOT fall back to an unranked search.

#### Scenario: Python without FTS5
- **WHEN** the engine starts under a Python whose `sqlite3` cannot create an FTS5 table
- **THEN** it exits non-zero with a message naming FTS5 and how to obtain a Python that has it
- **AND** no index file is created

#### Scenario: Same result on macOS and Linux
- **WHEN** the same repository content is indexed on a macOS machine and on a Linux machine
- **THEN** a search for the same query returns the same sources in the same order

### Requirement: Paths are stored repository-relative and normalised

The engine SHALL store every indexed path relative to the repository root, with `/`
separators and Unicode NFC normalisation, and SHALL NOT store an absolute path in the index.

#### Scenario: Repository cloned at different paths
- **WHEN** the same repository is cloned at two different absolute paths and indexed in each
- **THEN** every hit's path is identical in both, and neither index contains the clone location

#### Scenario: Accented file name
- **WHEN** a file name with accented characters is created on one operating system and indexed on another
- **THEN** the stored path is the NFC form, and a query containing the name's words finds it on both

### Requirement: The default corpus is every readable markdown file outside generated and log trees

With no project configuration the engine SHALL index every `.md` file under the repository
root except: `.git/`, `.set/`, dependency trees, `**/worktrees/**`, build and tool-cache
output, virtual environments, vendored third-party trees, agent-log trees, files whose
frontmatter marks them as an agent-session dump, and framework-deployed files whose content
still matches the deploy ledger. The engine SHALL NOT index `.jsonl` files. Archive
directories SHALL be indexed.

#### Scenario: A saved recording is indexed by its readable form
- **WHEN** a folder holds a recording as `<stem>.jsonl` and its readable transcript as `<stem>.md`
- **THEN** the `.md` file is indexed and the `.jsonl` file is not

#### Scenario: A readable transcript whose name contains "raw"
- **WHEN** a readable transcript is saved as `<date>-copilot-raw-part1.md` next to a `.jsonl` recording
- **THEN** it is indexed like any other markdown file

#### Scenario: Agent-session dump in the same folder
- **WHEN** a folder of saved recordings also holds an agent-session dump whose frontmatter `type` marks it as such
- **THEN** the dump is not indexed and the readable transcripts beside it are

#### Scenario: Build output carrying markdown
- **WHEN** a project contains `.next/standalone/**/*.md` or `.venv/lib/**/*.md`
- **THEN** none of those files is indexed

#### Scenario: Framework file edited by the project
- **WHEN** a file set-core deployed into `.claude/` has been edited by the project
- **THEN** it is indexed, while unedited deployed files are not

#### Scenario: Archived change
- **WHEN** a file sits under `openspec/changes/archive/`
- **THEN** it is indexed

### Requirement: Project exclusions add to the defaults

A project's `exclude` patterns SHALL be added to the default exclusions. A default exclusion
SHALL be dropped only by an explicit configuration key that names the opt-out. Exclusion
patterns SHALL be matched relative to the root they apply to.

#### Scenario: Adding one exclusion
- **WHEN** a project config sets `exclude` to a single pattern
- **THEN** that pattern is excluded and every default exclusion is still in force

#### Scenario: Dropping a default on purpose
- **WHEN** a project config names one default exclusion to keep out of the defaults
- **THEN** only that default is lifted, and the result page footer shows the active list without it

### Requirement: The index lives in the project's runtime directory and never in git

The engine SHALL keep the index and its sidecar files at `.set/kb/` inside the project. Before
creating or writing the index the engine SHALL verify with git that the index path is ignored,
and SHALL refuse to write it when it is not.

#### Scenario: Runtime directory not ignored
- **WHEN** `.set/` is not covered by the project's ignore rules
- **THEN** the engine refuses to build the index, names the path, and tells the caller to ignore it

#### Scenario: Index never staged
- **WHEN** a search has built or refreshed the index
- **THEN** `git status` lists no file under `.set/kb/`

### Requirement: The index refreshes incrementally on every search

Every search SHALL first bring the index up to date with the corpus: unchanged files skipped by
modification time and size, then by content hash; changed files re-chunked; deleted files
removed. The first build SHALL be atomic, so an interrupted build leaves no index file at the
final path. A change to the schema version, the SQLite version, or any configuration that
affects what is indexed or how rows are classified SHALL force a full rebuild. A caller SHALL
be able to skip the refresh explicitly.

#### Scenario: A new note is found immediately
- **WHEN** a markdown note is saved and a search for its words runs right after
- **THEN** the note is on the result page without any separate index command

#### Scenario: Interrupted first build
- **WHEN** the first build is killed before it finishes
- **THEN** no index exists at `.set/kb/index.db`, and the next search starts a fresh build

#### Scenario: Channel rules edited
- **WHEN** the channel rules in the project config change
- **THEN** the next search rebuilds the rows with the new classification instead of keeping old labels on unchanged files

#### Scenario: Measurement run without refresh
- **WHEN** a search is run with the no-reindex option
- **THEN** it queries the existing index and does not modify it

### Requirement: A fresh worktree starts from the main checkout's index

When a linked worktree has no index and the main checkout has one, the engine SHALL copy the
main checkout's index and refresh it incrementally instead of building from scratch.

#### Scenario: Search in a new worktree
- **WHEN** the first search runs in a newly created worktree whose main checkout has an index
- **THEN** the index is seeded from the main checkout and only files that differ are re-indexed

### Requirement: Concurrent callers share one index safely

At most one process SHALL refresh an index at a time. A search that cannot obtain the refresh
lock SHALL query the current snapshot without refreshing and SHALL say so on the result page.

#### Scenario: Two agents search at once
- **WHEN** two searches start in the same project at the same moment
- **THEN** one refreshes, the other returns results from the current snapshot with a note that it did not refresh, and neither fails

### Requirement: Search returns ranked sections, one slot per source

The engine SHALL rank sections with BM25 over weighted fields (heading path, heading, body),
SHALL collapse hits to one slot per source with a count of further matching sections, SHALL
mark sources whose identical content exists at other paths, and SHALL bound the page by the
number of distinct sources. Hits from the same file SHALL never occupy more than one slot.

#### Scenario: A file that owns the topic
- **WHEN** one file matches the query in six sections
- **THEN** it occupies one slot and reports five more matching sections

#### Scenario: Identical content at two paths
- **WHEN** the same content is stored at two paths with different source priorities
- **THEN** the higher-priority path is returned and the hit is marked as having a duplicate

### Requirement: Channels classify sources by root-scoped rules

A project SHALL be able to declare named channels as ordered rules, each scoped to one or more
roots with optional include patterns; the first matching rule SHALL decide a file's channel.
A rule without roots SHALL be rejected as a configuration error. Every hit SHALL carry its
channel.

#### Scenario: Rule without roots
- **WHEN** a channel rule is configured with include patterns but no roots
- **THEN** loading the configuration fails and names the rule

#### Scenario: Same folder name under a different root
- **WHEN** a channel rule covers `meetings/**` under one root and a file `meetings/x.md` exists under another root
- **THEN** that file is not classified into the channel

### Requirement: A project can reserve part of the page for named channels

A project SHALL be able to name the channels of a reserved lane and the share of the page
reserved for it. With no lane channels configured there SHALL be no reserved lane. A caller
SHALL be able to disable the lane for one search.

#### Scenario: Client voice buried by planning documents
- **WHEN** a project reserves half the page for its client channel and a query matches many planning documents and a few client e-mails
- **THEN** client e-mails occupy their reserved share of the page even where planning documents score higher

#### Scenario: No lane configured
- **WHEN** a project configures no lane channels
- **THEN** ranking is by score alone and no file type receives a reserved share

### Requirement: A project can capture a scope from the path and filter by it

A project SHALL be able to declare scope patterns containing a `{scope}` placeholder; at index
time the engine SHALL store the captured value with each chunk. A search restricted to a scope
value SHALL return only sources carrying that value. Every hit SHALL show its scope when it has
one.

#### Scenario: Searching one client's folder
- **WHEN** a project declares a scope pattern over its client folders and a search is restricted to one client's value
- **THEN** no hit from another client's folder appears on the page

#### Scenario: Pattern without placeholder
- **WHEN** a scope pattern lacks `{scope}`
- **THEN** loading the configuration fails and names the pattern

### Requirement: The upstream licence notice travels with the engine

The engine package SHALL contain the upstream MIT licence in full — copyright line and
permission notice — together with the upstream repository and commit it derives from and the
lineage of the port. Every module ported from upstream logic SHALL carry a one-line attribution
pointing at that notice; modules written new SHALL NOT carry it.

#### Scenario: Auditing a ported module
- **WHEN** a reviewer opens a module whose logic was ported from upstream
- **THEN** its first line points at the notice file, and the notice file contains the full MIT text and the upstream commit
