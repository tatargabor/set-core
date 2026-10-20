## IN SCOPE

- The two sources of an agent's flow — derived from the project's openspec tree,
  declared by the producer's stage order — and the precedence between them.
- The artifact→stage mapping for a derived change.
- The session→change inference over the session's own record, its bounded reads, and
  the archive anchor that bounds recency.

## OUT OF SCOPE

- The fleet strip's rendering of a resolved stage (visual vocabulary is the screen's).
- Anything the project declares through the project-status contract beyond the stage
  order and per-purpose change names it already publishes.

## ADDED Requirements

### Requirement: A session's own finished change stays finished
The stage resolver SHALL weigh candidates for an agent's change by recency of address,
with one exception: when the most recent positionable candidate is NOT archived, and
another candidate derives to `archive` while carrying at least half the leader's
tail-window mention weight, the archived candidate SHALL be resolved instead. A change
the session completed SHALL therefore remain `archive` until the session's newer work
outweighs the finished change's record.

#### Scenario: A drive-by mention of another session's active change
- **WHEN** a session archived its own change, and its record's most recent invocation
  match names an ACTIVE change belonging to a different session, with the archived
  change's tail mention weight at least half the active one's
- **THEN** the agent's position resolves to `archive`, not to the other change's stage

#### Scenario: A genuine switch to new work
- **WHEN** a session left a change behind and its recent record names the new change
  with more than twice the abandoned change's tail mention weight
- **THEN** the new change's stage resolves, and the abandoned change's archive state
  does not anchor the strip to finished work

### Requirement: The inference reads bounded windows and memoizes counts, never content
The session→change inference SHALL read at most a bounded head and tail window of the
session's own record, SHALL match only invocation-shaped occurrences of change names,
and SHALL memoize per-slug mention counts and slugs only. Transcript content SHALL NOT
be held in memory past a read, logged, or persisted.

#### Scenario: A session record is read for many polls
- **WHEN** the fleet payload resolves stages repeatedly against an unchanged record
- **THEN** the windows are read once per record state, and the memo holds only slugs
  and their counts

### Requirement: Derived position comes from the artifacts, and gaps are named
A change's position SHALL derive from its artifacts alone (archive layout including the
date-prefixed form; numbered-task progress; design/proposal presence), first rule wins.
A change name that no artifact backs SHALL resolve to a named gap (`no-position`), never
to a guessed stage; a project with no openspec tree SHALL resolve to `no-flow`; an
unmatched agent in a project with changes in flight SHALL resolve to `join-failed`, and
in a project with none to `nothing-started`.

#### Scenario: An inferred name with no artifacts
- **WHEN** the record names a change the project's tree has never carried
- **THEN** the agent's stage is a gap with reason `no-position`, not the flow's first
  stage
