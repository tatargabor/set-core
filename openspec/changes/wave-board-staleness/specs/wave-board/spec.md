## ADDED Requirements

### Requirement: A board's staleness is measured in commits since its last change

The tool SHALL compute, for each job:

- **manual open items:** items whose status is neither `done` nor `skipped`, and which either
  have no evidence or are `blocked`. These are the items `sync` cannot move.
- **the last change:** the newest of every item's `updated` and the job file's `reviewed.at`;
  failing both, the job's `created` date, read as midnight UTC.
- **commits since the change:** `git rev-list --count --since=<last change> HEAD` in the
  repository root. When there is no parseable last change, or git fails, this SHALL be null,
  never 0.
- **stale:** true when there is at least one manual open item and the commits since the change
  are at least `SET_WAVEBOARD_STALE_COMMITS` (default 3).

`set-wave-board stale [<job>...]` SHALL print each job's figures. With `--json` it SHALL print
one object per job: `job`, `last_change`, `commits_since_change`, `manual_open` (a list of
`id`, `status`, `title`, `wave`) and `stale`. It SHALL NOT write anything.

#### Scenario: Commits after the change make a board with manual items stale

- **WHEN** a job has one item with no evidence at `todo`, and 3 commits are made after its
  `updated`
- **THEN** `stale --json` reports `commits_since_change` 3, that item under `manual_open`, and
  `stale` true

#### Scenario: The board's own commit is not enough

- **WHEN** a job's item is set by hand and the job file is then committed once
- **THEN** `stale` is false

#### Scenario: Only items sync cannot move are manual

- **WHEN** a job holds a `todo` item with no evidence, a `blocked` item with evidence, a
  `doing` item with evidence, and a `done` item with no evidence
- **THEN** `manual_open` lists the first two and not the others

#### Scenario: A board whose items all have evidence is never stale

- **WHEN** every open item of a job has evidence and is not `blocked`, however many commits
  follow
- **THEN** `stale` is false

#### Scenario: Not measurable is null, not zero

- **WHEN** no item carries a parseable `updated`, the job has no `reviewed` and no `created`
- **THEN** `commits_since_change` is null and `stale` is false

### Requirement: An agent can record that a board was reviewed

`set-wave-board reviewed <job>` SHALL set `reviewed` to `{"at": <now, ISO UTC>, "by": <host
label>}` at the top level of the job file, and change nothing else in it. The `reviewed` field
SHALL NOT be part of the content that is hashed and pushed. A review SHALL therefore never make
a job pending a push, and `sync` SHALL keep the field as it is.

#### Scenario: A review resets staleness

- **WHEN** a job is stale and `reviewed` is run for it
- **THEN** `stale` reports `commits_since_change` 0 and `stale` false

#### Scenario: A review does not cause a push

- **WHEN** a job's payload has been recorded as pushed and `reviewed` is then run and `sync` runs
- **THEN** `pending` does not list the job, and the job file still carries the `reviewed` stamp

### Requirement: The Stop hook asks for a review of a stale board

Under the same silence rules as the push reminder, `set-hook-waveboard` SHALL also evaluate each
job's staleness. The silence rules are: its own continuation, `SET_WAVEBOARD_PUSH=off`, no
repository, a linked worktree, no `docs/waveboard/`, and any error.

For each stale job not reminded within the review backoff, it SHALL include a review reminder.
The backoff is `SET_WAVEBOARD_REVIEW_SECONDS`, default 14 400, with the timestamp in
`.set/waveboard/<job>.review-nag`. The reminder SHALL name:
- the number of commits since the board's last change;
- up to 20 manual open items, each with id, status and title, followed by the count of the rest;
- the `set-wave-board set <job> <item> <status>` command;
- the `set-wave-board reviewed <job>` command.

`SET_WAVEBOARD_REVIEW=off` SHALL silence only the review reminder.

The hook SHALL print at most one `{"decision":"block","reason":...}` per Stop. When a push and a
review are both due, one block SHALL carry the push procedure first and the review list after
it.

#### Scenario: A stale board blocks the stop with its items

- **WHEN** a stale job with no page URL has manual open items, and the hook runs in the main
  checkout
- **THEN** it prints one block whose reason names the commits since, each manual item's id, and
  both commands

#### Scenario: The review backs off on its own clock

- **WHEN** the hook gave a review reminder for a job and runs again within the review backoff
- **THEN** it prints nothing for that job's review

#### Scenario: Both due, one block

- **WHEN** a job is both pending a push and stale
- **THEN** the hook prints exactly one block, and its reason holds the push procedure before
  the review list

#### Scenario: The review alone can be switched off

- **WHEN** `SET_WAVEBOARD_REVIEW=off` and a job is stale but not pending
- **THEN** the hook prints nothing

#### Scenario: A worktree is still skipped

- **WHEN** the Stop event comes from a linked worktree of a repository with a stale job
- **THEN** the hook prints nothing
