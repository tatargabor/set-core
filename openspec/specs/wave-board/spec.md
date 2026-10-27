# wave-board Specification

## Purpose
The live execution status of a multi-step job that runs in waves: a tracked job file per job,
status derived from evidence by a hook-run sync, the agent's own report as the fast lane, and a
read-only Artifact page whose database only the agent writes.

## Requirements

### Requirement: A job is a tracked registration file

Each job SHALL be one JSON file at `docs/waveboard/<job>.json` in the consumer repository,
tracked in git, with `schema` equal to `set-wave-board/1`, a slug `job`, a `title`, an
`artifact_url` (null until the board page is published), a `created` date, and an ordered list
of `waves`, each with an `id`, a `title` and an ordered list of `items`. Each item SHALL carry
`id`, `title`, `status` (one of `todo`, `doing`, `done`, `blocked`, `skipped`), `evidence`
(null or an evidence object), `note`, `updated` and `by`.

The file SHALL NOT contain an absolute path. A path inside it is relative to the repository
root, and another project is named by its registry name.

#### Scenario: Creating a job and adding an item

- **WHEN** `set-wave-board init <job> --title T` runs and then
  `add <job> --wave w0 --item a --title A` runs
- **THEN** `docs/waveboard/<job>.json` exists with one wave `w0` holding item `a` at status
  `todo`

#### Scenario: Evidence that is malformed is refused when added

- **WHEN** `add` is given evidence of an unknown type, or one missing a required field
- **THEN** the command exits non-zero and the job file is unchanged

### Requirement: Status is derived from evidence

`sync` SHALL evaluate each item's evidence in the repository root
(`git rev-parse --show-toplevel`) and derive a status from it:

- `openspec-tasks` (`path`): every box checked → `done`, some → `doing`, none → `todo`; when
  the path is gone but `openspec/changes/archive/*-<change>/tasks.md` exists → `done`.
- `path-exists` (`path`): the path exists → `done`.
- `commit` (`grep`): `git log --grep` on `HEAD` finds a commit → `done`.

Absence of evidence SHALL NOT be a verdict: a missing path, a missing tasks file with no
archive, or no matching commit leaves the item's status as it is. Absence cannot tell "not yet"
from "not on this machine", and reporting the second as the first would undo a correct status.

#### Scenario: Partly checked tasks file

- **WHEN** an item's `openspec-tasks` file has some boxes checked and some not
- **THEN** sync sets the item to `doing`

#### Scenario: Archived change

- **WHEN** the change directory is gone and an archived copy of its `tasks.md` exists
- **THEN** sync sets the item to `done`

#### Scenario: No evidence yet

- **WHEN** an item's `path-exists` path does not exist and the item was set to `doing` by hand
- **THEN** sync leaves it at `doing`

### Requirement: Evidence wins, except a manual block or skip

When evidence yields a status, that status SHALL replace the item's status, with one exception:
an item whose status is `blocked` or `skipped` SHALL keep it. A block or a skip is a human
decision that no evidence can see.

#### Scenario: An agent's premature done is corrected

- **WHEN** an item was set to `done` by hand and its tasks file still has unchecked boxes
- **THEN** sync sets it to `doing`

#### Scenario: A blocked item stays blocked

- **WHEN** an item is `blocked` and its evidence says `done`
- **THEN** sync leaves it `blocked`

### Requirement: Evidence from another project is resolved by registry name

Evidence of type `project` SHALL name a project and carry nested evidence; the nested evidence
SHALL be evaluated with that project's root as the base. The name SHALL be resolved through the
set-core registry (`SET_CORE_REGISTRY`, default `~/.config/set-core/projects.json`). When the
name is not registered on this machine, or its path does not exist, the item's status SHALL be
left unchanged and the item SHALL be reported as unresolved. Nested `project` evidence SHALL be
refused.

#### Scenario: A registered project

- **WHEN** the named project is registered and its nested evidence is satisfied
- **THEN** sync sets the item to `done`

#### Scenario: A project not registered here

- **WHEN** the named project is not in this machine's registry
- **THEN** the item's status is unchanged and sync reports it as unresolved

### Requirement: Sync is idempotent and writes the database payload

`sync` SHALL rewrite a job file only when its content changed, with stable formatting, and
SHALL change an item's `updated` and `by` only when its status changed. It SHALL write the
database payload to `.set/waveboard/<job>.state.json` — `{schema, job, title, waves,
synced_at, synced_by, content_hash}` — only when the content hash differs from the payload
already there. When the job has an `artifact_url` and the payload's hash differs from the last
pushed hash, it SHALL print `PUSH <job> <artifact_url> <payload-path>` on standard output.
The tool SHALL keep `.set/waveboard/` out of git on its own.

#### Scenario: A second sync changes nothing

- **WHEN** sync runs twice with no change in evidence or in the job file
- **THEN** the second run rewrites neither file and, once the first payload has been recorded
  as pushed, prints no `PUSH` line

### Requirement: The push is the agent's act, recorded per machine

Only the agent can write the Artifact database, so the tool SHALL NOT attempt it. After the
agent writes the payload as document `state` in collection `board`, `set-wave-board pushed
<job> --version N` SHALL record the pushed hash and the database version in
`.set/waveboard/<job>.pushed.json`. `pending` SHALL list every job with an `artifact_url` whose
current payload hash differs from the recorded one.

#### Scenario: Push cycle

- **WHEN** a job's payload changed, then `pushed` is recorded for it
- **THEN** `pending` lists it before the record and does not list it after

### Requirement: A Stop hook makes the agent push

`set-hook-waveboard` SHALL run on the Stop event. It SHALL exit 0 without output when
`stop_hook_active` is true, outside a git repository, in a linked git worktree (unless
`SET_WAVEBOARD_PUSH=worktree`), when `docs/waveboard/` does not exist, or when
`SET_WAVEBOARD_PUSH=off`. Otherwise it SHALL run sync quietly and, for each pending job not
reminded within the backoff (default 30 minutes, timestamp in `.set/waveboard/<job>.nag`),
print one `{"decision":"block","reason":...}` whose reason is the exact push procedure: the
`ArtifactData` `set` call with the URL, `collection=board`, `doc_id=state`, the payload path,
and `if_version` (the last recorded version, or omitted when none is recorded), what to do on
a version conflict, and the `pushed` command to run after. It SHALL NOT use the network and
SHALL finish well inside its timeout.

#### Scenario: The hook's own continuation does not loop

- **WHEN** the Stop event carries `stop_hook_active: true`
- **THEN** the hook prints nothing and exits 0

#### Scenario: A linked worktree is not the board's source

- **WHEN** the Stop event comes from a linked git worktree of a repository with a pending job
- **THEN** the hook prints nothing

#### Scenario: Backoff

- **WHEN** the hook blocked for a job and runs again within the backoff with the job still
  pending
- **THEN** it prints nothing

### Requirement: The board page is read-only and works offline

The page SHALL render waves, items and status chips, done and remaining counts per wave and
overall, and the last sync time and machine. It SHALL subscribe to `board/state` through the
`db` capability and SHALL fall back to the embedded `<script type="application/json"
id="seed">` when the database is unavailable. It SHALL NOT write. `set-wave-board render`
SHALL produce the page with the current payload as the seed.

#### Scenario: Offline render

- **WHEN** `render <job> -o board.html` runs and the file is opened without the platform
- **THEN** the page shows the job from the seed and says it is a snapshot

### Requirement: The hook reaches existing projects

`set-deploy-hooks` SHALL add `set-hook-waveboard` to the Stop array, and SHALL treat a settings
file without it as not canonical, so a project initialised before this capability receives it
on its next `set-project init`. The merge SHALL keep every project-owned hook, and running it
twice SHALL add the hook once. `install.sh` SHALL link `set-wave-board` and
`set-hook-waveboard` into the install directory it puts on `PATH`.

#### Scenario: A project that already has the base hooks and its own

- **WHEN** a settings file carries the base hooks and a project-owned Stop hook, and
  `set-deploy-hooks` runs twice
- **THEN** the project hook is still there and `set-hook-waveboard` appears exactly once

### Requirement: The board page offers a Kanban view

The page SHALL offer two views of the same `board/state` data, **Waves** (the existing wave
ladder) and **Kanban**, with a toggle between them. The choice SHALL be remembered per viewer
in browser storage; when storage is unavailable or empty the page SHALL show Waves and the
toggle SHALL still work for the visit.

The Kanban view SHALL show four columns in this order: to do, in progress, blocked, done —
each with its item count — and one card per item in the column of the item's status. A card
SHALL show the item id and title, the item's wave as a tag whose colour is stable per wave,
and the updated time and machine when present. A note SHALL be a collapsed card body the
reader can open. Skipped items SHALL NOT form a column: they SHALL sit in a collapsed strip
below the columns whose summary carries their count.

A wave filter SHALL narrow the Kanban view to one wave, with all waves as the default. When
the filter hides a blocked item, the filter control SHALL say how many blocked items it is
hiding, so a narrowed board never reads as calmer than the job is.

The view and the filter SHALL survive a live update. The Kanban view SHALL use no storage
beyond the view preference, SHALL NOT change the payload or the seed, and SHALL NOT write.

#### Scenario: The view choice is remembered

- **WHEN** a viewer switches to Kanban and the page is opened again in the same browser
- **THEN** the page opens on Kanban

#### Scenario: No browser storage

- **WHEN** reading or writing browser storage throws or returns nothing
- **THEN** the page opens on Waves and the toggle still switches views for the visit

#### Scenario: Items land in their status column

- **WHEN** the state holds items that are to do, in progress, blocked, done and skipped
- **THEN** each of the first four appears as a card in its column with the column count
  matching, and the skipped item appears only inside the collapsed skipped strip, whose
  summary shows the count

#### Scenario: A card carries its wave and a folded note

- **WHEN** an item in wave `w2` has a note
- **THEN** its card shows a `w2` tag and the note is hidden until the reader opens it

#### Scenario: The filter does not hide a blocked item silently

- **WHEN** the filter is set to one wave and another wave holds a blocked item
- **THEN** only that wave's cards are shown and the filter control states the number of
  blocked items outside the filter

#### Scenario: A live update keeps the reader's place

- **WHEN** a new `board/state` snapshot arrives while Kanban is shown with a wave filter set
- **THEN** the page re-renders the new data in Kanban with the same filter

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
