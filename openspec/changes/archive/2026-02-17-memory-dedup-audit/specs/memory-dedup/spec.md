## ADDED Requirements

### Requirement: Audit command reports memory health
The `set-memory audit` command SHALL list all memories, compute pairwise similarity using `difflib.SequenceMatcher`, cluster near-duplicates using union-find, and print a diagnostic report including: total memory count, number of duplicate clusters, number of redundant entries, estimated unique count, dedup ratio percentage, and the top duplicate clusters with entry counts and content previews.

#### Scenario: Audit with duplicates present
- **WHEN** the memory store contains memories with >75% content similarity
- **THEN** `set-memory audit` prints a report showing duplicate clusters, redundant entry count, and content previews of the largest clusters

#### Scenario: Audit with no duplicates
- **WHEN** all memories have <75% content similarity to each other
- **THEN** `set-memory audit` prints a report showing 0 duplicate clusters and 0 redundant entries

#### Scenario: Audit with custom threshold
- **WHEN** `set-memory audit --threshold 0.9` is run
- **THEN** only clusters with >90% similarity are reported

#### Scenario: Audit JSON output
- **WHEN** `set-memory audit --json` is run
- **THEN** the output is a JSON object with keys: `total`, `clusters`, `redundant`, `unique`, `dedup_ratio`, and `top_clusters` (array of objects with `count`, `preview`, and `ids`)

#### Scenario: Audit with empty store
- **WHEN** the memory store is empty or shodh-memory is not installed
- **THEN** the command exits 0 with a message indicating no memories to audit (or empty JSON if `--json`)

### Requirement: Dedup command removes duplicate memories
The `set-memory dedup` command SHALL identify duplicate clusters (using the same algorithm as audit), select a survivor per cluster using a composite score (access_count, importance, content length, recency), and delete all other cluster members. Before deleting, it SHALL merge tags from all cluster members into the survivor by deleting and re-creating the survivor memory with the union of all tags.

#### Scenario: Dedup with dry-run
- **WHEN** `set-memory dedup --dry-run` is run
- **THEN** the command prints what would be deleted (cluster count, redundant count, survivor IDs) without modifying any memories, and outputs JSON with `dry_run: true`

#### Scenario: Dedup execution
- **WHEN** `set-memory dedup` is run (without `--dry-run`)
- **THEN** duplicate memories are deleted, survivor tags are merged, and the command prints JSON with `deleted_count` and `merged_count`

#### Scenario: Dedup with custom threshold
- **WHEN** `set-memory dedup --threshold 0.85` is run
- **THEN** only clusters with >85% similarity are processed

#### Scenario: Dedup interactive mode
- **WHEN** `set-memory dedup --interactive` is run and stdin is a TTY
- **THEN** for each duplicate cluster, the command displays the cluster members (ID prefix, content preview, access_count, importance) and prompts the user to `[k]eep best / [s]kip / [q]uit` before proceeding

#### Scenario: Interactive fallback when not a TTY
- **WHEN** `set-memory dedup --interactive` is run and stdin is NOT a TTY
- **THEN** the command falls back to `--dry-run` behavior and prints a warning

#### Scenario: Dedup with no duplicates
- **WHEN** no memories exceed the similarity threshold
- **THEN** the command prints JSON with `deleted_count: 0` and `merged_count: 0`

#### Scenario: Dedup tag merging
- **WHEN** a cluster has 3 memories with tags `[a,b]`, `[b,c]`, `[c,d]`
- **THEN** the survivor is re-created with tags `[a,b,c,d]` (union of all tags)

### Requirement: Survivor selection uses composite scoring
Within each duplicate cluster, the survivor SHALL be selected by composite score: `access_count * 10 + importance * 5 + len(content) / 100`. Tiebreaker: most recent `created_at`.

#### Scenario: Higher access count wins
- **WHEN** a cluster has memory A (access_count=5, importance=0.4) and memory B (access_count=1, importance=0.4) with similar content lengths
- **THEN** memory A is selected as survivor

#### Scenario: Longer content wins when other factors equal
- **WHEN** a cluster has memory A (100 chars) and memory B (250 chars) with equal access_count and importance
- **THEN** memory B is selected as survivor

### Requirement: Graceful degradation
If shodh-memory is not installed, both `audit` and `dedup` commands SHALL exit silently with code 0 and appropriate empty output (empty report or `{"deleted_count": 0}`).

#### Scenario: Shodh-memory not installed
- **WHEN** `set-memory audit` or `set-memory dedup` is run without shodh-memory installed
- **THEN** the command exits 0 with no error output
