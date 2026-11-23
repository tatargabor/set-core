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
SHALL change an item's `updated` only when its status changed. It SHALL write the
database payload to `.set/waveboard/<job>.state.json` — `{schema, job, title, waves,
synced_at, content_hash}` — only when the content hash differs from the payload
already there. Neither this payload, the combined payload, nor the combined seed SHALL carry a
machine name. When the job has an `artifact_url` and the payload's hash differs from the last
pushed hash, it SHALL print `PUSH <job> <artifact_url> <payload-path>` on standard output.
The tool SHALL keep `.set/waveboard/` out of git on its own.

#### Scenario: A second sync changes nothing

- **WHEN** sync runs twice with no change in evidence or in the job file
- **THEN** the second run rewrites neither file and, once the first payload has been recorded
  as pushed, prints no `PUSH` line

#### Scenario: The payload names no machine

- **WHEN** sync writes the state payload
- **THEN** the payload has no `synced_by` field and carries `synced_at`

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

`set-hook-waveboard` SHALL run on the Stop event and SHALL be OFF unless the machine opts in:
it SHALL exit 0 without output, without running sync, unless `SET_WAVEBOARD_PUSH` is `on`,
`1`, `true`, `yes` or `worktree`. An unset, empty or unrecognised value is off. When on, it
SHALL also exit 0 without output when `stop_hook_active` is true, outside a git repository, in
a linked git worktree (unless `SET_WAVEBOARD_PUSH=worktree`), or when `docs/waveboard/` does
not exist. Otherwise it SHALL run sync quietly and decide per job, from the push
class sync reports, whether to ask for the push now:

- `first` (no push recorded on this machine) or `milestone` (since the last push a wave has
  had every item `done` or `skipped`, or an item has turned `blocked`): ask, unless reminded
  within the backoff (default 30 minutes, `SET_WAVEBOARD_NAG_SECONDS`, timestamp in
  `.set/waveboard/<job>.nag`);
- `progress` (item statuses, titles, waves or dependencies changed, no milestone): ask only
  when the job's oldest pending target was last pushed at least
  `SET_WAVEBOARD_DEBOUNCE_SECONDS` ago (default 3600) and the job was not reminded within that
  time either;
- `notes` (only notes, `updated` / `by` stamps or evidence definitions changed): never ask.

A job's board document and its combined-board document SHALL be decided together, by the
strongest class among them, and asked for in the same block. When at least one job is due it
SHALL print one `{"decision":"block","reason":...}` whose reason is the exact push procedure:
the `ArtifactData` `set` call with the URL, `collection=board`, `doc_id=state`, the payload
path, and `if_version` (the last recorded version, or omitted when none is recorded), what to do
on a version conflict, and the `pushed` command to run after. It SHALL NOT use the network and
SHALL finish well inside its timeout.

`pushed` SHALL record, with the hash and version, the marks the next push is classed against
— the finished waves, the blocked items and a hash of the visible substance — but only when the
recorded hash is the current payload's own. A record without marks SHALL class the next change
as `progress`, never as `notes`.

#### Scenario: Off unless the machine opts in

- **WHEN** a repository has a job with a pending push and `SET_WAVEBOARD_PUSH` is unset
- **THEN** the hook prints nothing, exits 0, and does not run sync

#### Scenario: Opted in, the reminder works as before

- **WHEN** the same repository is stopped in with `SET_WAVEBOARD_PUSH=on`
- **THEN** the hook blocks with the push procedure

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

#### Scenario: Routine progress is batched

- **WHEN** a job was pushed less than `SET_WAVEBOARD_DEBOUNCE_SECONDS` ago and an item has
  since moved from `todo` to `doing`
- **THEN** the hook prints nothing, and `set-wave-board pending` still lists the job

#### Scenario: A milestone is asked for at once

- **WHEN** an item turned `blocked`, or the last open item of a wave became `done` or
  `skipped`, since the job's last push
- **THEN** the hook blocks with the push procedure without waiting for the debounce

#### Scenario: A notes-only change is never asked for

- **WHEN** only an item's note changed since the job's last push
- **THEN** the hook prints nothing, even with both backoffs at zero, and the change goes with
  the next push that is asked for

#### Scenario: The board and the combined document travel together

- **WHEN** a job's combined-board document has never been pushed and its board has only a
  notes change
- **THEN** one block asks for both pushes

### Requirement: The board page is read-only and works offline

The page SHALL render waves, items and status chips, done and remaining counts per wave and
overall, and the last sync time. It SHALL NOT show a machine name. It SHALL subscribe to
`board/state` through the `db` capability and SHALL fall back to the embedded `<script
type="application/json" id="seed">` when the database is unavailable. Each item SHALL offer the
board's `assignees` in a select, showing the `board/assignees` document's value for that item over
the item's own `assignee`. The page's only write SHALL be the `board/assignees` document; it SHALL
NOT write `board/state`. `set-wave-board render` SHALL produce the page with the current payload as
the seed.

#### Scenario: Offline render

- **WHEN** `render <job> -o board.html` runs and the file is opened without the platform
- **THEN** the page shows the job from the seed and says it is a snapshot

#### Scenario: A viewer picks an assignee

- **WHEN** a viewer chooses "Dana" on item H1 while the database is available
- **THEN** `board/assignees` gets `H1: "Dana"`, every open view shows Dana on H1, and a later
  push of `board/state` does not undo it

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

`set-wave-board reviewed <job>` SHALL set `reviewed` to `{"at": <now, ISO UTC>}` at the top level
of the job file, and change nothing else in it. A legacy `reviewed.by` SHALL be dropped on the
next write of the job file. The `reviewed` field SHALL NOT be part of the content that is hashed
and pushed. A review SHALL therefore never make a job pending a push, and `sync` SHALL keep the
field as it is.

#### Scenario: A review resets staleness

- **WHEN** a job is stale and `reviewed` is run for it
- **THEN** `stale` reports `commits_since_change` 0 and `stale` false

#### Scenario: A review records no machine

- **WHEN** `reviewed` is run for a job whose file carries a legacy `reviewed.by`
- **THEN** the job file's `reviewed` holds `at` and no `by`

#### Scenario: A review does not cause a push

- **WHEN** a job's payload has been recorded as pushed and `reviewed` is then run and `sync` runs
- **THEN** `pending` does not list the job, and the job file still carries the `reviewed` stamp

### Requirement: The Stop hook asks for a review of a stale board

Under the same silence rules as the push reminder, `set-hook-waveboard` SHALL also evaluate each
job's staleness. The silence rules are: `SET_WAVEBOARD_PUSH` not opted in (unset or off), its own
continuation, no repository, a linked worktree, no `docs/waveboard/`, and any error.

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

### Requirement: Items carry an assignee chosen from the board's list

A job file SHALL carry a board-level `assignees` list of names and MAY carry an item-level
`assignee`. `init --assignees`, `assignees`, `add --assignee` and `assign` SHALL maintain them;
`assign <job> <item> -` SHALL clear the item's assignee. Both fields SHALL be part of the payload.
No command SHALL write a machine name into the job file or the payload; a legacy item `by` SHALL
be dropped on the next write.

#### Scenario: Assign and clear

- **WHEN** `assign job H1 András` runs and then `assign job H1 -`
- **THEN** the item first has `assignee: "András"` and then no assignee, and each change marks the
  payload for a push

#### Scenario: No hostname reaches the payload

- **WHEN** `sync` runs on a job file whose items still carry `by`
- **THEN** the written job file and payload contain no `by` on any item

### Requirement: Items record what they wait on

An item SHALL be able to carry `waits`, a list of objects `{kind, who, text, ref}` where `kind` is `decision` or
`blocker`. `wait` SHALL append one, or replace in place the wait with the same `ref`; `unwait` SHALL
remove the one named by `--ref`, all with `--all`, or the only one when the item has one. A wait SHALL
NOT change the item's status. Empty text, an unknown item and an unknown ref SHALL be usage errors.
Waits SHALL be part of the payload.

#### Scenario: A decision and a blocker on one item

- **WHEN** `wait job H2.3 --decision "Price on the site?" --who Dana --ref G2` and
  `wait job H2.3 --blocker "Run migration 0019" --who Dana --ref G9` run
- **THEN** the item carries both waits in that order, its status is unchanged, and the payload
  carries them after `sync`

#### Scenario: Same ref replaces

- **WHEN** a second `wait` uses a ref that is already on the item
- **THEN** the earlier wait is replaced in its position, not duplicated

### Requirement: The page lists every open wait by person

The board page SHALL show a "Waiting on people" panel above the waves, with one group per `who`
(unnamed waits grouped together), decisions before blockers, each line naming the item id, the ref
and the text. Waits on skipped items SHALL be left out; waits on done items SHALL be shown. The
summary SHALL count decisions and blockers, and each row and Kanban card SHALL show its own waits.
The panel SHALL be hidden when nothing waits.

#### Scenario: Two people, two groups

- **WHEN** the payload has waits on Dana and on András
- **THEN** the panel shows two groups with their counts, and the summary shows the totals

### Requirement: Status pills fit their column

In the Waves view, the status column SHALL be as wide as the widest pill in the wave, so no pill label
overflows its pill or its column, and the rows of a wave SHALL stay aligned. At 320px no part of the
page SHALL scroll horizontally.

#### Scenario: "in progress" fits

- **WHEN** a wave holds an in-progress item
- **THEN** its pill's text stays inside the pill, measured at 1280, 375 and 320px

### Requirement: Viewers set statuses and answer waits on the page

The board page SHALL offer every item's status as a select and SHALL write a pick to `board/statuses`
as `{item: {status, at}}`. A pick SHALL be shown over the pushed status only while it is newer than the
item's `updated`. Each wait in the "Waiting on people" panel SHALL offer one button per `options` entry
and a free-text field, and SHALL write an answer to `board/answers` under `<item>|<ref>` (or
`<item>|#<index>` without a ref). The page SHALL NOT write `board/state`.

#### Scenario: Pick a status and answer a question

- **WHEN** a viewer sets H1.2 to done, clicks "C" on wait P1 and sends "99 000 Ft" as the other answer to G2
- **THEN** `board/statuses` holds `H1.2: done`, `board/answers` holds `H0.1|P1: C` and `H2.3|G2: 99 000 Ft`,
  and the page shows the new status and both answers

### Requirement: Page choices come back through import

`import <job> --dir DIR` SHALL apply each status pick newer than its item's last change as a manual
status, and each answer newer than the wait's recorded one as `answer` and `answered`; it SHALL print one
`STATUS` or `ANSWER` line per change and change nothing on a second run with the same documents.

#### Scenario: An old pick is ignored

- **WHEN** the statuses document holds a pick older than the item's last change
- **THEN** import leaves that item's status as it is

### Requirement: The page speaks the board's language

A job file SHALL accept `lang` (`en` or `hu`), set by `lang <job> <lang>`; it SHALL be in the payload only when
set. With `hu`, the page SHALL show its own labels in Hungarian, including "Egyéb" for the free-text answer.

#### Scenario: Hungarian board

- **WHEN** `lang job hu` runs and the page renders the payload
- **THEN** the panel is titled "Kire várunk" and the in-progress pill reads "folyamatban"

### Requirement: The share step names the editors and the owner account

*Asked for by the owner on 2026-11-08. A board must sit in an Artifact that everyone on the team can write.*

The tool SHALL read a machine-local editor list. Its path is `SET_WAVEBOARD_EDITORS`, or failing that
`~/.config/set-core/waveboard-editors.json`. The list is a JSON object with `owner_account` (a string) and `editors`
(a list of strings), and optionally `combined_url` and `projects` (see the combined board). The tool SHALL NOT write the
list, except that `combined-link` sets the `combined_url` key and leaves every other key as it was. It SHALL NOT copy
any address from the list into the job file, the payload or a log line.

The tool SHALL read the account the session is signed in as from `oauthAccount.emailAddress` in
`$CLAUDE_CONFIG_DIR/.claude.json`, or in `~/.claude.json` when that variable is unset. When it cannot be read, the
account SHALL be reported as unknown.

The share step SHALL be printed by:
- `init` when it is given `--artifact-url`;
- `link`;
- `share [<job>...]`, for every named job, or for every job when none is named.

For a job with a page URL, the step SHALL name the URL, the claude.ai Share action, every editor with edit access, the
owner account, and the session's account. It SHALL say whether the session's account matches the owner account. For a
job without a page URL, `share` SHALL say that the board is not published.

When the list is missing or malformed, the step SHALL say so and show the expected shape. That SHALL NOT be an error:
the command's exit status is unchanged. With `--json` the same facts SHALL be returned as a `share` object.

#### Scenario: Linking a board names the editors

- **WHEN** the editor list names an owner and two editors, and `link <job> <url>` runs
- **THEN** the output carries a share line with the URL, both editors with edit access, and the owner account

#### Scenario: The session is not the owner account

- **WHEN** the session's account differs from `owner_account`
- **THEN** the share step says that the accounts differ, and names both

#### Scenario: No editor list

- **WHEN** no editor list exists at the resolved path
- **THEN** `link` still succeeds, and its output says the list is missing and where it belongs

#### Scenario: Nothing is persisted

- **WHEN** `init --artifact-url`, `link` and `sync` have run with an editor list present
- **THEN** neither the job file nor the payload contains any address from the list

### Requirement: A refused push asks for edit access

The push procedure in the Stop hook SHALL tell the agent what to do when the write is refused because its account
cannot write the Artifact. It SHALL say:
- ask the owner account named in the editor list (or, without a list, the account that published the board) for edit
  access through claude.ai Share;
- say so in one line, and continue.

The procedure SHALL NOT advise `SET_WAVEBOARD_PUSH=off`. The switch itself SHALL keep working.

#### Scenario: The procedure names the owner

- **WHEN** a job is pending, the editor list names an owner, and the hook blocks
- **THEN** the reason names that owner account and edit access, and does not contain `SET_WAVEBOARD_PUSH=off`

### Requirement: An item can depend on another board's item

An item MAY carry `depends_on`: a list of references, each `{"job": J, "item": I}` with an optional `"project": P`.
- Without `project`, a reference points into the same repository.
- With `project`, the project SHALL be resolved through the set-core registry, the same way `project` evidence is.
- Job and item SHALL be valid ids.
- A reference to the item itself SHALL be refused.

Dependencies SHALL be set in three ways:
- `add --depends-on <ref>`, which may be repeated;
- `depend <job> <item> <ref>...`;
- `undepend <job> <item> <ref>...`.

A reference is written `[project:]job/item`. A malformed reference SHALL exit 2 and leave the file unchanged. Adding a
reference that is already there SHALL change nothing.

#### Scenario: Adding a cross-project dependency

- **WHEN** `depend j a other:k/b` runs
- **THEN** item `a` of job `j` carries `{"project":"other","job":"k","item":"b"}` in `depends_on`

#### Scenario: A malformed reference

- **WHEN** `depend j a not-a-ref` runs
- **THEN** the command exits 2 and the job file is unchanged

### Requirement: A dependency is met only by a done item, and never by an unknown one

A reference SHALL be met when the item it names exists and its status is `done`. It SHALL be unmet in every other
case:
- any other status, `skipped` included;
- the project is not registered here, or its directory is missing;
- the job file is missing or unreadable, or the item is missing.

An unmet reference that cannot be resolved SHALL carry a reason and a null status.

#### Scenario: The prerequisite is done

- **WHEN** an item depends on an item whose status is `done`
- **THEN** the dependency is met and the item is not waiting

#### Scenario: The prerequisite was skipped

- **WHEN** the referenced item is `skipped`
- **THEN** the dependency is unmet and reports status `skipped`

#### Scenario: An unregistered project

- **WHEN** a reference names a project that is not in this machine's registry
- **THEN** the dependency is unmet with a reason, never met

### Requirement: The payload carries what each item waits on and what it blocks

`sync` SHALL add two computed lists to each item of the payload:
- `waiting_on`, when the item is neither `done` nor `skipped`: its unmet references, each with `status` and `reason`;
- `blocks`: every item on a board of any registered project, or of this repository, whose `depends_on` names this
  item, each with its project, job, item and status.

Both lists SHALL be part of the hashed content. This repository SHALL be matched by every registry name whose path
resolves to its root, and by references without a project. Neither list SHALL be written into the job file, and the
scan SHALL NOT run git.

#### Scenario: The other board finishes

- **WHEN** a pushed board has an item waiting on another board's item, and that item becomes `done`
- **THEN** the next sync drops the reference from `waiting_on`, the content hash changes, and the job is pending a push

#### Scenario: Shown on both boards

- **WHEN** item `a` of job `j` depends on item `b` of job `k`, in the same repository
- **THEN** the payload of `j` lists `k/b` under `a`'s `waiting_on`, and the payload of `k` lists `j/a` under `b`'s
  `blocks`

### Requirement: A waiting item cannot be started by report

`set <job> <item> doing` and `set <job> <item> done` SHALL exit 2 and name the unmet references when the item has any.
With `--force`, the status SHALL be set. `todo`, `blocked` and `skipped` SHALL always be allowed. A status that sync
derives from evidence SHALL NOT be guarded.

#### Scenario: Refused without force

- **WHEN** an item waits on an unmet reference and `set <job> <item> done` runs
- **THEN** the command exits 2, names the reference, and the job file is unchanged

#### Scenario: Forced

- **WHEN** the same command runs with `--force`
- **THEN** the item's status becomes `done`

### Requirement: The page shows waits-on and blocks

The board page SHALL draw an item that is `todo` and has a non-empty `waiting_on` as blocked:
- with the blocked chip colour;
- in the blocked Kanban column;
- as a blocked segment, counted as blocked.

It SHALL add a "waits on" chip listing each reference as `project/job/item` with its status or reason. An item that is
`doing` with a non-empty `waiting_on` SHALL keep its status and also show the chip. An item with a non-empty `blocks`
SHALL show a "blocks N" chip whose tooltip lists the references, and says that they were read on the machine that
synced. A payload without these fields SHALL render as it did before.

#### Scenario: A waiting todo item

- **WHEN** the state holds a `todo` item with one entry in `waiting_on`
- **THEN** the Waves view shows it with the blocked chip and a waits-on chip, and the Kanban view shows it in the
  blocked column

#### Scenario: An old payload

- **WHEN** the state has no `waiting_on` or `blocks` fields
- **THEN** every item renders in its own status, as before

### Requirement: `overview` is the combined view over the team's projects

`set-wave-board overview` SHALL read the `docs/waveboard/*.json` of every registered project inside the team scope (the
editor list's `projects`; every registered project when no scope is set, or with `--all`) and print:
- one line per board, with its counts, its waiting items and the items it blocks;
- one line per dependency edge, saying met or unmet, with the reason when unresolved.

With `--json` it SHALL return `boards` and `edges`. A file that cannot be read SHALL be listed with a reason, never left
out. It SHALL NOT write anything.

#### Scenario: Two projects linked by one edge

- **WHEN** project A's board has an item depending on project B's item, which is `doing`
- **THEN** `overview --json` lists both boards and one edge from A to B with `met` false

### Requirement: The combined board is scoped to the team's projects

*Asked for by the owner on 2026-11-08: the combined board covers the team's development, not every project on the
machine.*

The editor list MAY carry `projects`: a list of registry names or `fnmatch` patterns. A repository SHALL be inside the
team scope when one of its registry names matches. Nothing outside the scope SHALL reach the combined board. Without
`projects`, nothing SHALL be pushed to it, and `combined-page` SHALL exit 2 and say how to set the scope. The page is
shared with other people, and one machine holds more projects than one team works on.

#### Scenario: A project outside the scope

- **WHEN** `combined_url` is set and the repository's registry name matches no entry of `projects`
- **THEN** sync writes no combined document and prints no `PUSH-COMBINED`, and `pending` lists none

#### Scenario: No scope

- **WHEN** `combined_url` is set and `projects` is absent
- **THEN** nothing goes to the combined board and `combined-page` exits 2

### Requirement: Every board in scope is one document on the combined board

When the editor list has a `combined_url` and the repository is inside the team scope, `sync` SHALL write
`.set/waveboard/<job>.combined.json`. That payload holds the board's content plus `project` (the matching registry name)
and `artifact_url`, with its own content hash. `sync` SHALL print `PUSH-COMBINED <job> <url> boards/<project>--<job>
<payload>` when this machine has not recorded a push of that hash to that URL.

`pushed <job> --combined --version N` SHALL record the push with the URL. A different `combined_url` SHALL make every
board pending again. `pending` SHALL list combined pushes as `PENDING-COMBINED`.

The Stop hook SHALL include the combined push in its one block, with collection `boards`, the document id, `if_version`
when one is recorded, and the `pushed --combined` command.

#### Scenario: The push cycle on the combined board

- **WHEN** a board in scope is synced, pushed with `--combined`, and then changes
- **THEN** it is pending before the record, not pending after it, and pending again after the change

#### Scenario: One block for both pushes

- **WHEN** a board is pending on its own page and on the combined board
- **THEN** the hook prints one block naming `collection=board, doc_id=state` and `collection=boards,
  doc_id=<project>--<job>`

### Requirement: The combined page lists every board and the edges between them

`combined-page [-o FILE] [--bare]` SHALL render `templates/waveboard/combined.html`, seeded with every in-scope board
this machine can read, `waiting_on` and `blocks` included. `combined-link <url>` SHALL record the URL and print the
share step.

The page SHALL subscribe to collection `boards` through the `db` capability and fall back to the seed. It SHALL show:
- totals over every board;
- the dependency edges, unmet first, each with its target's status, or with the reason it is unresolved;
- one row per board, grouped by project, with a proportional status bar, its counts and its blocked, waiting and
  blocks figures;
- in each row, a fold holding the board's open items and their waits-on chips.

It SHALL NOT write. When the live data has not answered within 10 seconds, it SHALL say so.

#### Scenario: Two boards in scope linked by an edge

- **WHEN** `combined-page` runs with two in-scope projects whose boards are linked by one dependency, and a third
  project outside the scope
- **THEN** the seed holds the two boards, with `waiting_on` and `blocks` filled in, and not the third
