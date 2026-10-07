## IN SCOPE
- A per-project health check of the search runtime, configuration, ignore status and corpus
- A deterministic findability check for saved recordings and for notes a project names
- A retrieval eval over a project-owned golden set with a control arm
- The re-measure gate that guards moving a project from its own engine to the shared one
- A differential check of the shared engine against the reference engine on a synthetic corpus

## OUT OF SCOPE
- Measuring whether search improves a downstream task (answers, plans, bug fixes)
- Generating golden sets from a project's tickets or correspondence
- Storing any project's golden set, baseline or results in set-core

## ADDED Requirements

### Requirement: Doctor reports whether search works in this project

`set-kb doctor` SHALL check and report: Python version, FTS5 and tokenizer availability, SQLite
version, configuration validity, that the index path is ignored by git, index presence and
freshness, indexed file and chunk counts per root and channel, and excluded file counts per
exclusion rule. It SHALL exit non-zero when any check blocks search from working.

#### Scenario: Healthy project
- **WHEN** doctor runs in a project with a valid config, FTS5 available and `.set/` ignored
- **THEN** it exits zero and prints the counts per root, channel and exclusion rule

#### Scenario: Excluded share made visible
- **WHEN** an exclusion rule removes most of a root's files
- **THEN** doctor prints that rule with its count, so a silently shrunken corpus is visible

### Requirement: Saved recordings and named notes are findable

`set-kb findability` SHALL discover every saved recording — a readable `.md` file in a folder
that holds a `.jsonl` recording with the same stem or the same date-and-part prefix — and every
file matching the project's configured findability globs. For each it SHALL verify that the
file is indexed, naming the exclusion rule when it is not, and SHALL run a query built only from
the file's title or first heading, with stopwords removed and no words taken from its path,
reporting whether the file appears within the top k results. It SHALL report counts and list
every miss. It SHALL use no model and no network.

#### Scenario: Recording hidden by an exclusion
- **WHEN** a readable transcript sits next to its `.jsonl` recording inside a folder an exclusion rule matches
- **THEN** findability reports the transcript as not indexed and names the rule, and exits non-zero

#### Scenario: Recording retrievable by its title
- **WHEN** a readable transcript titled with its meeting topic is indexed
- **THEN** a query made from that title returns it within the top 10, and it counts as found

#### Scenario: A note the project wants guaranteed
- **WHEN** a project lists `docs/decisions/**/*.md` in its findability globs
- **THEN** every decision note is checked the same way as a recording

### Requirement: Retrieval eval runs over a project-owned golden set with a control arm

`set-kb eval` SHALL read a golden set of `{id, q, targets[]}` pairs from the project (default
`set/knowledge/kb-golden.json`), accept multi-target pairs, and report Recall@k, MRR, rank-1,
top-3 and top-5. It SHALL run a control arm with a fixed control query and print that query. A
search that fails SHALL count as a miss and SHALL be reported separately; it SHALL NOT be
removed from the denominator. A fixture in another shape SHALL be rejected with an error.

#### Scenario: Failed search
- **WHEN** one of 50 golden queries raises an error
- **THEN** the denominator stays 50, the pair counts as a miss, and the failure is listed

#### Scenario: Control arm
- **WHEN** eval runs with the control arm
- **THEN** the report shows the control query verbatim and its recall next to the real arm's

#### Scenario: Lane disabled for measurement
- **WHEN** eval runs with the lane quota disabled
- **THEN** ranking ignores the reserved lane for every query in that run

### Requirement: The shared engine matches the reference engine on a synthetic corpus

set-core SHALL carry a synthetic fixture corpus containing no project content, the queries to
run over it, and the result pages the reference engine produced for them. The shared engine's
test suite SHALL compare its pages with those recorded pages and SHALL fail on any difference in
returned sources or their order.

#### Scenario: Ranking drift
- **WHEN** a change to the shared engine alters the order of sources for a fixture query
- **THEN** the differential test fails and names the query and both orders

### Requirement: Moving a project onto the shared engine is gated by a re-measurement

A project that replaces its own engine with the shared one SHALL, on one frozen corpus snapshot
and with its existing configuration unchanged, run its golden set through the reference engine
and the shared engine, each with the reserved lane on and off. The move SHALL proceed only when,
in every arm, the shared engine's hit count is not lower than the reference engine's and its MRR
is not lower by more than 0.005. The baseline SHALL be produced on that snapshot during the
gate, not quoted from an earlier measurement. A per-query page comparison SHALL be kept with the
result in the project's repository. A later change of corpus defaults SHALL be measured as a
separate step.

#### Scenario: Gate passes
- **WHEN** the shared engine finds at least as many targets as the reference in both arms and its MRR is within 0.005
- **THEN** the project may point its callers at `set-kb`

#### Scenario: Gate fails
- **WHEN** the shared engine finds fewer targets than the reference in either arm
- **THEN** the project keeps its own engine and the differing queries are listed for diagnosis

#### Scenario: Corpus change measured on its own
- **WHEN** a project that passed the gate switches to the new default corpus that includes saved recordings
- **THEN** its eval is re-run and recorded as a corpus change, separately from the engine move
